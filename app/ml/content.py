"""Multi-channel content representation.

The previous content model concatenated every metadata field into one string and
ran a single TF-IDF over it. That has a structural flaw: a 60-word plot summary
contributes ~60 terms while the genre list contributes three, so genre agreement
is effectively drowned out no matter how the text is repeated. Repeating genres
"3x" only nudges it.

Here each field is vectorised in its own space, L2-normalised *within* that space,
then scaled by an explicit weight before the channels are concatenated. Every
channel therefore contributes a bounded, tunable share of the final similarity,
independent of how verbose it happens to be.

Channels, in descending influence:

=============  ======  ==========================================================
channel        weight  signal
=============  ======  ==========================================================
genres          1.00   the strongest single predictor of taste agreement
keywords        0.85   TMDB plot keywords -- themes rather than words
tags            0.85   MovieLens folk tags ("mindfuck", "based on a book")
director        0.75   authorship; a strong stylistic fingerprint
cast            0.60   shared leads, damped so ensembles do not dominate
overview        0.55   free text, the noisiest channel
era             0.30   release decade, for period affinity
language        0.25   original language, mostly separating non-English cinema
=============  ======  ==========================================================

Content similarity is what makes cold start and brand-new releases work at all: a
film released last week has no collaborative signal whatsoever, but it has genres,
a director and a plot.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
from typing import Iterable, Optional, Sequence

import numpy as np
from scipy.sparse import csr_matrix, hstack

from app.ml.linalg import row_normalize

logger = logging.getLogger(__name__)

CHANNEL_WEIGHTS = {
    "genres": 1.00,
    "keywords": 0.85,
    "tags": 0.85,
    "director": 0.75,
    "cast": 0.60,
    "overview": 0.55,
    "era": 0.30,
    "language": 0.25,
}

_PUNCTUATION = re.compile(r"[^\w\s]")
_YEAR_SUFFIX = re.compile(r"\s*\(\d{4}\)\s*$")


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return _PUNCTUATION.sub(" ", str(text)).lower().strip()


def _entity_tokens(value: Optional[str]) -> str:
    """Turns a comma-separated name list into single tokens.

    "Christopher Nolan, Emma Thomas" becomes "christopher_nolan emma_thomas" so
    that two films sharing a director match on one strong token rather than on the
    first name alone -- otherwise every "Michael" matches every other "Michael".
    """
    if not value:
        return ""
    tokens = []
    for part in str(value).split(","):
        cleaned = _PUNCTUATION.sub("", part).strip().lower()
        if cleaned:
            tokens.append(cleaned.replace(" ", "_"))
    return " ".join(tokens)


def build_channel_documents(rows: Sequence[dict]) -> dict[str, list[str]]:
    """Projects catalogue rows into one document list per channel."""
    documents: dict[str, list[str]] = {name: [] for name in CHANNEL_WEIGHTS}

    for row in rows:
        genres = (row.get("genres") or "").replace("|", " ")
        documents["genres"].append(_clean(genres) if genres != "(no genres listed)" else "")
        documents["keywords"].append(_entity_tokens(row.get("keywords")))
        documents["tags"].append(_clean(row.get("user_tags")))
        documents["director"].append(_entity_tokens(row.get("director")))
        documents["cast"].append(_entity_tokens(row.get("cast_list")))

        title = _YEAR_SUFFIX.sub("", row.get("title") or "")
        overview = f"{_clean(title)} {_clean(row.get('overview'))} {_clean(row.get('tagline'))}"
        documents["overview"].append(overview.strip())

        year = row.get("release_year")
        documents["era"].append(f"decade_{int(year) // 10 * 10}s" if year else "")

        language = (row.get("original_language") or "").lower()
        documents["language"].append(f"lang_{language}" if language else "")

    return documents


class ContentModel:
    """Weighted multi-channel TF-IDF over catalogue metadata."""

    def __init__(self, weights: Optional[dict[str, float]] = None, max_features: int = 60_000):
        self.weights = dict(weights or CHANNEL_WEIGHTS)
        self.max_features = max_features

        self.matrix: Optional[csr_matrix] = None
        self.vectorizers: dict[str, TfidfVectorizer] = {}
        self.movie_ids: Optional[np.ndarray] = None
        self._movie_id_to_index: Optional[dict[int, int]] = None

    def fit(self, rows: Sequence[dict]) -> "ContentModel":
        # Imported here, not at module scope: fitting happens offline in the
        # training pipeline, and the API must never pay scikit-learn's 84 MB.
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.movie_ids = np.array([int(row["id"]) for row in rows], dtype=np.int64)
        self._movie_id_to_index = None
        documents = build_channel_documents(rows)

        blocks = []
        for channel, weight in self.weights.items():
            corpus = documents[channel]
            if not any(corpus):
                logger.warning("Content channel %r is empty; skipping", channel)
                continue

            # Free text benefits from bigrams; token channels are already atomic.
            is_text = channel == "overview"
            # Dropping singletons denoises a large corpus, but on a small one it can
            # prune every term and abort the build. Channels like "era" legitimately
            # have one document per value.
            min_df = 2 if len(corpus) >= 500 else 1
            vectorizer = TfidfVectorizer(
                stop_words="english" if is_text else None,
                ngram_range=(1, 2) if is_text else (1, 1),
                max_features=self.max_features if is_text else None,
                min_df=min_df,
                sublinear_tf=True,
                dtype=np.float32,
            )
            try:
                block = vectorizer.fit_transform(corpus)
            except ValueError as exc:
                # Raised when pruning leaves an empty vocabulary. One degenerate
                # channel must not take the whole representation down with it.
                logger.warning("Content channel %r produced no terms (%s); skipping", channel, exc)
                continue

            # Normalising inside the channel is the whole point: it decouples a
            # channel's influence from its verbosity.
            block = row_normalize(block) * np.sqrt(weight)
            blocks.append(block.astype(np.float32))
            self.vectorizers[channel] = vectorizer
            logger.info(
                "  channel %-9s weight %.2f -> %s features",
                channel, weight, f"{block.shape[1]:,}",
            )

        if not blocks:
            raise ValueError("No usable content channels; is the catalogue enriched?")

        self.matrix = row_normalize(hstack(blocks).tocsr()).astype(np.float32)
        logger.info(
            "Content matrix: %s titles x %s features (%s nnz)",
            f"{self.matrix.shape[0]:,}", f"{self.matrix.shape[1]:,}", f"{self.matrix.nnz:,}",
        )
        return self

    # ------------------------------------------------------------------- serving

    def profile_score(
        self,
        indices: Sequence[int],
        weights: Sequence[float],
    ) -> np.ndarray:
        """Cosine of every title against a weighted centroid of the profile."""
        if self.matrix is None:
            raise RuntimeError("Model is not trained or loaded.")
        indices = np.asarray(indices, dtype=np.int64)
        if indices.size == 0:
            return np.zeros(self.matrix.shape[0], dtype=np.float32)

        weight_vector = np.asarray(weights, dtype=np.float32).reshape(1, -1)
        centroid = np.asarray(weight_vector @ self.matrix[indices], dtype=np.float32).ravel()
        centroid = row_normalize(centroid)
        return np.asarray(self.matrix @ centroid, dtype=np.float32).ravel()

    def similar_items(self, index: int, limit: int = 12) -> list[tuple[int, float]]:
        if self.matrix is None:
            raise RuntimeError("Model is not trained or loaded.")
        scores = np.asarray(self.matrix @ self.matrix[index].T.toarray(), dtype=np.float32).ravel()
        scores[index] = -np.inf
        top = np.argpartition(-scores, limit)[:limit]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]

    def movie_id_to_index(self) -> dict[int, int]:
        if self._movie_id_to_index is None:
            self._movie_id_to_index = {int(mid): i for i, mid in enumerate(self.movie_ids)}
        return self._movie_id_to_index

    # --------------------------------------------------------------- persistence

    def save(self, directory: str, name: str = "content.pkl") -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "wb") as handle:
            pickle.dump(
                {
                    "weights": self.weights,
                    "max_features": self.max_features,
                    "matrix": self.matrix,
                    "movie_ids": self.movie_ids,
                    # Deliberately not persisted: unpickling a TfidfVectorizer
                    # requires scikit-learn, and nothing at serving time
                    # transforms new text. Refitting rebuilds them anyway.
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info("Saved content model to %s", path)
        return path

    @classmethod
    def load(cls, directory: str, name: str = "content.pkl") -> "ContentModel":
        with open(os.path.join(directory, name), "rb") as handle:
            state = pickle.load(handle)
        model = cls(weights=state["weights"], max_features=state["max_features"])
        model.matrix = state["matrix"]
        model.movie_ids = state["movie_ids"]
        return model


def fetch_catalogue_rows(min_rating_count: int = 0) -> list[dict]:
    """Reads the catalogue fields the content model needs, in id order."""
    from app.pipeline.ingest import connect

    connection = connect()
    try:
        connection.row_factory = None
        cursor = connection.execute(
            """
            SELECT id, title, genres, keywords, user_tags, director, cast_list,
                   overview, tagline, release_year, original_language
            FROM movies
            WHERE rating_count >= ? OR poster_path IS NOT NULL
            ORDER BY id
            """,
            (min_rating_count,),
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def build_and_save(output_dir: Optional[str] = None) -> dict:
    """Builds the content model from the live catalogue and persists it."""
    from app.config.settings import settings

    output_dir = output_dir or settings.MODELS_DIR
    rows = fetch_catalogue_rows()
    logger.info("Building content model over %s catalogue rows", f"{len(rows):,}")
    model = ContentModel().fit(rows)
    model.save(output_dir)
    return {"titles": len(rows), "features": int(model.matrix.shape[1])}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(build_and_save())
