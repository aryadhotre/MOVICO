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

# Score-blend weights, selected by the grid search in ``app.ml.train`` against the
# held-out evaluation slice rather than picked by hand. Collaborative evidence
# leads; the quality prior is what keeps the list from drifting into well-matched
# but poorly-regarded films. Re-tune with:
#     python -m app.ml.train --reuse-models
WEIGHTS = {
    "ials": 0.50,
    "item_knn": 0.28,
    "content": 0.12,
    "quality": 0.10,
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


#: Score assigned to items a model has no evidence about. Zero would be wrong:
#: in z-space zero means "exactly average", which would let a title the
#: collaborative model has never seen outrank one it has actively scored low.
NO_EVIDENCE = -1.0


def _standardise(
    scores: np.ndarray,
    mask: Optional[np.ndarray] = None,
    fill: float = NO_EVIDENCE,
) -> np.ndarray:
    """Z-scores a signal over the entries that actually carry it.

    ``mask`` matters more than it looks. Only ~44k of the ~96k catalogue titles
    have collaborative signal; the rest sit at a structural zero. Standardising
    across all of them puts a huge spike at the mean, which collapses the standard
    deviation and inflates the real scores to a range of roughly -16..+65. At that
    spread the quality prior and the novelty term — worth ~2.6 between them — are
    swamped by a factor of fourteen, and the novelty control silently does nothing.

    Computing the statistics over the masked subset keeps every component on a
    comparable scale, so the blend weights mean what they say.
    """
    if mask is None:
        valid = scores
        result = np.empty_like(scores, dtype=np.float32)
        target = slice(None)
    else:
        valid = scores[mask]
        result = np.full(scores.shape, fill, dtype=np.float32)
        target = mask

    if valid.size == 0:
        return np.full(scores.shape, fill, dtype=np.float32)

    std = float(valid.std())
    if std < 1e-9:
        result[target] = 0.0
        return result

    result[target] = (valid - float(valid.mean())) / std
    # Clip the tail so one outlier cannot dominate the blend.
    return np.clip(result, -6.0, 6.0, out=result)


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
                       release_year, poster_path, genres, rating_count, vote_count
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
        self.recommendable = np.zeros(count, dtype=bool)

        genre_rows: list[int] = []
        genre_cols: list[int] = []
        genre_lookup: dict[str, int] = {}

        for slot, row in enumerate(rows):
            (movie_id, bayes, popularity, trending, year, poster,
             genres, rating_count, vote_count) = row
            self.movie_ids[slot] = movie_id
            self.quality[slot] = bayes or 0.0
            self.popularity[slot] = popularity or 0.0
            self.trending[slot] = trending or 0.0
            self.release_year[slot] = year or 0
            # A title with no artwork renders as a broken card.
            self.displayable[slot] = bool(poster)
            # Recommending is a stronger claim than listing. A title nobody has
            # rated cannot be stood behind, and surfacing it is what made the
            # novelty control look broken -- it dredged up unrated obscurities
            # rather than under-seen good films. Browse still shows everything.
            self.recommendable[slot] = bool(poster) and (
                (rating_count or 0) >= 3 or (vote_count or 0) >= 20
            )

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
        collab_known = self.collab_slot >= 0
        if collab_idx.size:
            vector = self.ials.fold_in(collab_idx, collab_conf)
            collab_scores = self.ials.score_all(vector)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            scattered[collab_known] = collab_scores[self.collab_slot[collab_known]]
            standardised = _standardise(scattered, collab_known)
            components["ials"] = standardised
            total += WEIGHTS["ials"] * standardised

            knn_scores = self.knn.score(collab_idx, collab_conf)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            scattered[collab_known] = knn_scores[self.collab_slot[collab_known]]
            standardised = _standardise(scattered, collab_known)
            components["item_knn"] = standardised
            total += WEIGHTS["item_knn"] * standardised

        # --- content --------------------------------------------------------------
        if content_idx.size:
            content_known = self.content_slot >= 0
            content_scores = self.content.profile_score(content_idx, content_conf)
            scattered = np.zeros(len(self.movie_ids), dtype=np.float32)
            scattered[content_known] = content_scores[self.content_slot[content_known]]
            standardised = _standardise(scattered, content_known)
            components["content"] = standardised
            total += WEIGHTS["content"] * standardised

        # --- priors ---------------------------------------------------------------
        # Quality and novelty are defined for every title, so they need no mask.
        quality = _standardise(self.quality, fill=0.0)
        components["quality"] = quality
        total += WEIGHTS["quality"] * quality

        if novelty > 0:
            # Penalise the head without rewarding the void. Clamping at zero means
            # a blockbuster is pushed down while an obscure title gets no bonus for
            # obscurity alone. A symmetric penalty turns the dial into a race to the
            # bottom: at high novelty it surfaces films nobody has rated, which is
            # noise rather than discovery.
            head = np.maximum(_standardise(np.log1p(self.popularity), fill=0.0), 0.0)
            total -= novelty * 0.95 * head

        # --- filters --------------------------------------------------------------
        blocked = set(int(m) for m in exclude) | {int(mid) for mid, _ in rated}
        mask = self.recommendable.copy()
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

        Three terms, because any two of them fail:

        * **quality** alone returns a museum of acknowledged classics;
        * **momentum** alone returns whatever is being hyped this week, which on a
          catalogue that ingests upcoming releases means a page of films nobody has
          actually seen;
        * **audience** anchors both to titles with a real viewership, which is what
          keeps a first impression credible.

        Weighted toward proven titles, then diversified so two new users do not see
        an identical page.
        """
        score = (
            0.45 * _standardise(self.quality, fill=0.0)
            + 0.30 * _standardise(np.log1p(self.popularity), fill=0.0)
            + 0.25 * _standardise(np.log1p(self.trending), fill=0.0)
        )

        mask = self.recommendable.copy()
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

        combined += 0.10 * _standardise(self.quality, fill=0.0)
        combined[~self.recommendable] = -np.inf
        combined[slot] = -np.inf

        take = min(limit, int(self.recommendable.sum()) - 1)
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
            "recommendable_titles": int(self.recommendable.sum()),
            "collaborative_titles": int((self.collab_slot >= 0).sum()),
            "factors": int(self.ials.factors),
            "weights": WEIGHTS,
        }


# Process-wide singleton. Artifacts are hundreds of megabytes, so they are loaded
# once and shared across requests.
engine = RecommendationEngine()
