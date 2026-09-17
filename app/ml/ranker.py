"""Serving-time recommendation engine.

Loads the trained artifacts once and answers requests from memory. Three problems
this layer exists to solve, beyond simply combining model scores:

**Two index spaces.** The collaborative models only know titles that had enough
MovieLens ratings to learn from (~44k). The catalogue is larger and includes every
2023+ release, which by definition has no collaborative signal at all. The
canonical space here is the *catalogue*, with collaborative scores scattered into
it where they exist, so a brand-new film can still surface on content and quality
evidence instead of being silently unreachable.

**Relevance is not enough.** Ranking purely by predicted relevance produces ten
near-identical films -- technically accurate and useless. A maximal-marginal-
relevance pass trades a little relevance for spread, and a novelty term keeps the
same blockbusters from filling every slot for every user. This is the difference
between recommendations that feel "boring" and ones that feel considered.

**Explanations must be honest.** The attribution returned with each item is read
back out of the neighbourhood model: it names the profile titles that actually
contributed the most score, rather than finding a plausible-looking match after
the fact.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize

from app.config.settings import settings
from app.ml.content import ContentModel
from app.ml.ials import ImplicitALS
from app.ml.itemknn import ItemKNN

logger = logging.getLogger(__name__)

POSITIVE_THRESHOLD = 3.5
ALPHA = 18.0

# Score-blend weights. Collaborative evidence leads; the quality prior is what
# keeps the list from drifting into well-matched but poorly-regarded films.
WEIGHTS = {
    "ials": 0.46,
    "item_knn": 0.26,
    "content": 0.16,
    "quality": 0.12,
}

# Relevance/diversity trade-off for the MMR pass. 1.0 disables diversification.
MMR_LAMBDA = 0.82
# Candidates re-ranked before the final cut.
CANDIDATE_POOL = 320


@dataclass
class ScoredMovie:
    movie_id: int
    score: float
    rank: int
    components: dict[str, float] = field(default_factory=dict)
    because_of: list[tuple[int, float]] = field(default_factory=list)


def _standardise(scores: np.ndarray) -> np.ndarray:
    """Z-scores so heterogeneous model outputs can be blended on one scale."""
    std = float(scores.std())
    if std < 1e-9:
        return np.zeros_like(scores)
    return (scores - float(scores.mean())) / std


class RecommendationEngine:
    """Holds trained artifacts and catalogue arrays for in-memory scoring."""

    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = models_dir or settings.MODELS_DIR
        self._lock = threading.RLock()
        self.loaded = False
        self.loaded_at: Optional[float] = None
        self.load_error: Optional[str] = None

        self.ials: Optional[ImplicitALS] = None
        self.knn: Optional[ItemKNN] = None
        self.content: Optional[ContentModel] = None

        # Catalogue-space arrays, all aligned to self.movie_ids.
        self.movie_ids: Optional[np.ndarray] = None
        self.movie_index: dict[int, int] = {}
        self.collab_slot: Optional[np.ndarray] = None
        self.content_slot: Optional[np.ndarray] = None
        self.quality: Optional[np.ndarray] = None
        self.popularity: Optional[np.ndarray] = None
        self.trending: Optional[np.ndarray] = None
        self.release_year: Optional[np.ndarray] = None
        self.displayable: Optional[np.ndarray] = None
        self.genre_matrix: Optional[csr_matrix] = None

    # --------------------------------------------------------------------- load

    def load(self, force: bool = False) -> bool:
        """Loads artifacts and catalogue arrays. Safe to call concurrently."""
        with self._lock:
            if self.loaded and not force:
                return True
            try:
                self.ials = ImplicitALS.load(self.models_dir)
                self.knn = ItemKNN.load(self.models_dir)
                self.content = ContentModel.load(self.models_dir)
                self._load_catalogue()
                self.loaded = True
                self.loaded_at = time.time()
                self.load_error = None
                logger.info(
                    "Recommendation engine ready: %s catalogue titles, %s with collaborative signal",
                    f"{len(self.movie_ids):,}",
                    f"{int((self.collab_slot >= 0).sum()):,}",
                )
                return True
            except (FileNotFoundError, OSError, ValueError) as exc:
                self.loaded = False
                self.load_error = str(exc)
                logger.warning("Recommendation engine unavailable: %s", exc)
                return False

    def _load_catalogue(self) -> None:
        """Pulls the ranking columns into numpy arrays indexed by catalogue slot."""
        from app.pipeline.ingest import connect

        connection = connect()
        try:
            rows = connection.execute(
                """
                SELECT id, bayes_score, popularity_score, trending_score,
                       release_year, poster_path, genres
                FROM movies
                ORDER BY id
                """
            ).fetchall()
        finally:
            connection.close()

        count = len(rows)
        self.movie_ids = np.empty(count, dtype=np.int64)
        self.quality = np.zeros(count, dtype=np.float32)
        self.popularity = np.zeros(count, dtype=np.float32)
        self.trending = np.zeros(count, dtype=np.float32)
        self.release_year = np.zeros(count, dtype=np.int32)
        self.displayable = np.zeros(count, dtype=bool)

        genre_rows: list[int] = []
        genre_cols: list[int] = []
        genre_lookup: dict[str, int] = {}

        for slot, (movie_id, bayes, popularity, trending, year, poster, genres) in enumerate(rows):
            self.movie_ids[slot] = movie_id
            self.quality[slot] = bayes or 0.0
            self.popularity[slot] = popularity or 0.0
            self.trending[slot] = trending or 0.0
            self.release_year[slot] = year or 0
            # A title with no artwork renders as a broken card, so it never enters
            # a recommendation list.
            self.displayable[slot] = bool(poster)

            for genre in (genres or "").split("|"):
                genre = genre.strip()
                if not genre or genre == "(no genres listed)":
                    continue
                if genre not in genre_lookup:
                    genre_lookup[genre] = len(genre_lookup)
                genre_rows.append(slot)
                genre_cols.append(genre_lookup[genre])

        self.movie_index = {int(mid): i for i, mid in enumerate(self.movie_ids)}
        self.genre_matrix = normalize(
            csr_matrix(
                (np.ones(len(genre_rows), dtype=np.float32), (genre_rows, genre_cols)),
                shape=(count, max(len(genre_lookup), 1)),
            )
        )

        # Map catalogue slots onto each model's own index space.
        collab_lookup = self.ials.item_id_to_index()
        content_lookup = self.content.movie_id_to_index()
        self.collab_slot = np.full(count, -1, dtype=np.int64)
        self.content_slot = np.full(count, -1, dtype=np.int64)
        for slot, movie_id in enumerate(self.movie_ids):
            collab = collab_lookup.get(int(movie_id))
            if collab is not None:
                self.collab_slot[slot] = collab
            content = content_lookup.get(int(movie_id))
            if content is not None:
                self.content_slot[slot] = content

    # ------------------------------------------------------------------ scoring

    @staticmethod
    def _confidence(ratings: Sequence[float]) -> np.ndarray:
        """Maps star ratings to the confidence weights used during training."""
        values = np.asarray(ratings, dtype=np.float32)
        graded = (values - POSITIVE_THRESHOLD) / (5.0 - POSITIVE_THRESHOLD)
        return (ALPHA * (0.33 + 0.67 * np.clip(graded, 0.0, 1.0))).astype(np.float32)

    def _profile(self, rated: Sequence[tuple[int, float]]):
        """Splits a rating history into the arrays each model consumes."""
        liked = [(mid, value) for mid, value in rated if value >= POSITIVE_THRESHOLD]
        catalogue_slots = np.array(
            [self.movie_index[mid] for mid, _ in rated if mid in self.movie_index],
            dtype=np.int64,
        )

        collab_idx, collab_conf = [], []
        content_idx, content_conf = [], []
        for movie_id, value in liked:
            slot = self.movie_index.get(movie_id)
            if slot is None:
                continue
            confidence = float(self._confidence([value])[0])
            if self.collab_slot[slot] >= 0:
                collab_idx.append(int(self.collab_slot[slot]))
                collab_conf.append(confidence)
            if self.content_slot[slot] >= 0:
                content_idx.append(int(self.content_slot[slot]))
                content_conf.append(confidence)

        return (
            catalogue_slots,
            np.array(collab_idx, dtype=np.int64),
            np.array(collab_conf, dtype=np.float32),
            np.array(content_idx, dtype=np.int64),
            np.array(content_conf, dtype=np.float32),
        )

    def recommend(
        self,
        rated: Sequence[tuple[int, float]],
        limit: int = 20,
        exclude: Iterable[int] = (),
        diversity: float = 1.0,
        novelty: float = 0.0,
        genres: Optional[Sequence[str]] = None,
        min_year: Optional[int] = None,
    ) -> tuple[list[ScoredMovie], str]:
        """Ranks the catalogue for a rating history.

        ``diversity`` scales the MMR trade-off (0 = pure relevance, 1 = default),
        ``novelty`` in [0, 1] shifts weight from popular titles toward the tail.
        Returns the ranked items and the strategy name used.
        """
        if not self.loaded and not self.load():
            raise RuntimeError(f"Recommendation engine unavailable: {self.load_error}")

        catalogue_slots, collab_idx, collab_conf, content_idx, content_conf = self._profile(rated)

        if collab_idx.size == 0 and content_idx.size == 0:
            return self._cold_start(limit, exclude, genres, min_year), "cold_start"

        total = np.zeros(len(self.movie_ids), dtype=np.float32)
        components: dict[str, np.ndarray] = {}

        # --- collaborative latent -------------------------------------------------
        if collab_idx.size:
            vector = self.ials.fold_in(collab_idx, collab_conf)
            collab_scores = self.ials.score_all(vector)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            known = self.collab_slot >= 0
            scattered[known] = collab_scores[self.collab_slot[known]]
            standardised = _standardise(scattered)
            components["ials"] = standardised
            total += WEIGHTS["ials"] * standardised

            knn_scores = self.knn.score(collab_idx, collab_conf)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            scattered[known] = knn_scores[self.collab_slot[known]]
            standardised = _standardise(scattered)
            components["item_knn"] = standardised
            total += WEIGHTS["item_knn"] * standardised

        # --- content --------------------------------------------------------------
        if content_idx.size:
            content_scores = self.content.profile_score(content_idx, content_conf)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            known = self.content_slot >= 0
            scattered[known] = content_scores[self.content_slot[known]]
            standardised = _standardise(scattered)
            components["content"] = standardised
            total += WEIGHTS["content"] * standardised

        # --- priors ---------------------------------------------------------------
        quality = _standardise(self.quality)
        components["quality"] = quality
        total += WEIGHTS["quality"] * quality

        if novelty > 0:
            # Penalise well-known titles proportionally to log audience size.
            total -= novelty * 0.30 * _standardise(np.log1p(self.popularity))

        # --- filters --------------------------------------------------------------
        blocked = set(int(m) for m in exclude) | {int(mid) for mid, _ in rated}
        mask = self.displayable.copy()
        for movie_id in blocked:
            slot = self.movie_index.get(movie_id)
            if slot is not None:
                mask[slot] = False
        if min_year:
            mask &= self.release_year >= min_year
        if genres:
            wanted = self._genre_mask(genres)
            mask &= wanted
        total[~mask] = -np.inf

        # --- re-rank --------------------------------------------------------------
        pool_size = min(CANDIDATE_POOL, int(mask.sum()))
        if pool_size == 0:
            return [], "empty"
        pool = np.argpartition(-total, pool_size - 1)[:pool_size]
        pool = pool[np.argsort(-total[pool])]

        selected = self._mmr(pool, total, limit, diversity)

        results: list[ScoredMovie] = []
        for rank, slot in enumerate(selected, start=1):
            results.append(
                ScoredMovie(
                    movie_id=int(self.movie_ids[slot]),
                    score=float(total[slot]),
                    rank=rank,
                    components={
                        name: round(float(values[slot]), 4)
                        for name, values in components.items()
                    },
                    because_of=self._attribute(slot, collab_idx),
                )
            )
        return results, "hybrid"

    def _genre_mask(self, genres: Sequence[str]) -> np.ndarray:
        """Boolean mask of titles carrying any of the requested genres."""
        from app.pipeline.ingest import connect

        wanted = {g.strip().lower() for g in genres if g and g.strip()}
        if not wanted:
            return np.ones(len(self.movie_ids), dtype=bool)

        connection = connect()
        try:
            clause = " OR ".join(["LOWER(genres) LIKE ?"] * len(wanted))
            rows = connection.execute(
                f"SELECT id FROM movies WHERE {clause}",
                tuple(f"%{g}%" for g in wanted),
            ).fetchall()
        finally:
            connection.close()

        mask = np.zeros(len(self.movie_ids), dtype=bool)
        for (movie_id,) in rows:
            slot = self.movie_index.get(int(movie_id))
            if slot is not None:
                mask[slot] = True
        return mask

    def _mmr(
        self,
        pool: np.ndarray,
        scores: np.ndarray,
        limit: int,
        diversity: float,
    ) -> list[int]:
        """Maximal marginal relevance over the candidate pool.

        Each pick maximises ``lambda * relevance - (1 - lambda) * similarity to
        what is already chosen``, using genre overlap as the similarity. Without
        this the top of the list collapses onto one cluster -- ten Marvel films, or
        ten Kubrick films -- which reads as a broken recommender even when every
        individual score is correct.
        """
        limit = min(limit, pool.size)
        if diversity <= 0 or limit <= 1:
            return pool[:limit].tolist()

        lam = 1.0 - (1.0 - MMR_LAMBDA) * float(np.clip(diversity, 0.0, 1.0))

        block = self.genre_matrix[pool]
        similarity = np.asarray((block @ block.T).todense(), dtype=np.float32)
        np.fill_diagonal(similarity, 0.0)

        relevance = scores[pool]
        finite = relevance[np.isfinite(relevance)]
        if finite.size:
            spread = float(finite.max() - finite.min()) or 1.0
            relevance = (relevance - float(finite.min())) / spread

        chosen: list[int] = [0]
        remaining = set(range(1, pool.size))

        while len(chosen) < limit and remaining:
            candidates = np.fromiter(remaining, dtype=np.int64)
            penalty = similarity[np.ix_(candidates, np.array(chosen))].max(axis=1)
            marginal = lam * relevance[candidates] - (1.0 - lam) * penalty
            best = int(candidates[int(np.argmax(marginal))])
            chosen.append(best)
            remaining.discard(best)

        return pool[chosen].tolist()

    def _attribute(self, slot: int, collab_idx: np.ndarray) -> list[tuple[int, float]]:
        """Names the profile titles that contributed most to this item's score."""
        if collab_idx.size == 0 or self.collab_slot[slot] < 0:
            return []
        contributors = self.knn.top_contributors(
            int(self.collab_slot[slot]), collab_idx, limit=3
        )

        results: list[tuple[int, float]] = []
        for collab_index, weight in contributors:
            movie_id = int(self.ials.item_ids[collab_index])
            results.append((movie_id, round(float(weight), 4)))
        return results

    def _cold_start(
        self,
        limit: int,
        exclude: Iterable[int],
        genres: Optional[Sequence[str]],
        min_year: Optional[int],
    ) -> list[ScoredMovie]:
        """Ranking for a user with no usable ratings yet.

        Blends quality with current momentum rather than returning a raw
        popularity list, then diversifies, so two new users do not see an
        identical page.
        """
        score = 0.6 * _standardise(self.quality) + 0.4 * _standardise(np.log1p(self.trending))

        mask = self.displayable.copy()
        for movie_id in exclude:
            slot = self.movie_index.get(int(movie_id))
            if slot is not None:
                mask[slot] = False
        if min_year:
            mask &= self.release_year >= min_year
        if genres:
            mask &= self._genre_mask(genres)
        score[~mask] = -np.inf

        pool_size = min(CANDIDATE_POOL, int(mask.sum()))
        if pool_size == 0:
            return []
        pool = np.argpartition(-score, pool_size - 1)[:pool_size]
        pool = pool[np.argsort(-score[pool])]
        selected = self._mmr(pool, score, limit, diversity=1.0)

        return [
            ScoredMovie(movie_id=int(self.movie_ids[slot]), score=float(score[slot]), rank=rank)
            for rank, slot in enumerate(selected, start=1)
        ]

    # ----------------------------------------------------------------- similarity

    def similar(self, movie_id: int, limit: int = 12) -> list[ScoredMovie]:
        """Titles similar to one title, blending collaborative and content signal.

        Collaborative similarity captures "people who liked this also liked"; content
        similarity captures "this is the same kind of film". Either alone is
        noticeably worse: collaborative alone cannot handle new releases, and
        content alone returns sequels and little else.
        """
        if not self.loaded and not self.load():
            raise RuntimeError(f"Recommendation engine unavailable: {self.load_error}")

        slot = self.movie_index.get(int(movie_id))
        if slot is None:
            return []

        combined = np.zeros(len(self.movie_ids), dtype=np.float32)

        if self.collab_slot[slot] >= 0:
            neighbours = self.knn.similar_items(int(self.collab_slot[slot]), limit=200)
            if neighbours:
                scores = np.zeros(len(self.movie_ids), dtype=np.float32)
                for collab_index, weight in neighbours:
                    target = self.movie_index.get(int(self.ials.item_ids[collab_index]))
                    if target is not None:
                        scores[target] = weight
                combined += 0.6 * _standardise(scores)

        if self.content_slot[slot] >= 0:
            neighbours = self.content.similar_items(int(self.content_slot[slot]), limit=200)
            if neighbours:
                scores = np.zeros(len(self.movie_ids), dtype=np.float32)
                content_ids = self.content.movie_ids
                for content_index, weight in neighbours:
                    target = self.movie_index.get(int(content_ids[content_index]))
                    if target is not None:
                        scores[target] = weight
                combined += 0.4 * _standardise(scores)

        combined += 0.10 * _standardise(self.quality)
        combined[~self.displayable] = -np.inf
        combined[slot] = -np.inf

        take = min(limit, int(self.displayable.sum()) - 1)
        if take <= 0:
            return []
        top = np.argpartition(-combined, take - 1)[:take]
        top = top[np.argsort(-combined[top])]

        return [
            ScoredMovie(movie_id=int(self.movie_ids[s]), score=float(combined[s]), rank=rank)
            for rank, s in enumerate(top, start=1)
            if np.isfinite(combined[s])
        ]

    # ----------------------------------------------------------------- diagnostics

    def status(self) -> dict:
        if not self.loaded:
            return {"loaded": False, "error": self.load_error}
        return {
            "loaded": True,
            "loaded_at": self.loaded_at,
            "catalogue_titles": int(len(self.movie_ids)),
            "displayable_titles": int(self.displayable.sum()),
            "collaborative_titles": int((self.collab_slot >= 0).sum()),
            "factors": int(self.ials.factors),
            "weights": WEIGHTS,
        }


# Process-wide singleton. Artifacts are hundreds of megabytes, so they are loaded
# once and shared across requests.
engine = RecommendationEngine()
