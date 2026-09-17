"""Interaction dataset construction from the MovieLens archive.

The MovieLens ``ml-latest`` archive holds ~33.8M ratings. Loading that through the
ORM is what broke the previous ingestion pipeline, so training data never touches
SQLite: it is read straight from CSV with Arrow, compacted into fixed-width numpy
arrays, and cached as a single ``.npz`` artifact.

Only *aggregates* are written to the application database (see
``app.pipeline.ingest``). Live recommendations for real application users are
produced by folding their ratings into the trained item factors, so the serving
path never needs the historical rating rows.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.sparse import csr_matrix

logger = logging.getLogger(__name__)

# MovieLens ratings are half-star steps in [0.5, 5.0]; stored as rating*2 in uint8.
RATING_SCALE = 2.0

# A rating at or above this value is treated as a positive signal for ranking.
POSITIVE_THRESHOLD = 3.5


@dataclass
class Interactions:
    """A compacted user/item interaction set with contiguous internal indices.

    ``user_idx``/``item_idx`` are positions into ``user_ids``/``item_ids``, which
    hold the original MovieLens identifiers. Keeping both directions lets the
    serving layer translate between database movie ids and matrix columns.
    """

    user_idx: np.ndarray  # uint32
    item_idx: np.ndarray  # uint32
    rating: np.ndarray  # float32, original 0.5-5.0 scale
    timestamp: np.ndarray  # uint32, unix seconds
    user_ids: np.ndarray  # int32, original MovieLens userId per user index
    item_ids: np.ndarray  # int32, original MovieLens movieId per item index

    @property
    def n_users(self) -> int:
        return int(self.user_ids.shape[0])

    @property
    def n_items(self) -> int:
        return int(self.item_ids.shape[0])

    @property
    def n_interactions(self) -> int:
        return int(self.user_idx.shape[0])

    def item_id_to_index(self) -> dict[int, int]:
        return {int(mid): idx for idx, mid in enumerate(self.item_ids)}

    def describe(self) -> str:
        density = self.n_interactions / (self.n_users * self.n_items)
        return (
            f"{self.n_interactions:,} interactions | {self.n_users:,} users | "
            f"{self.n_items:,} items | density {density * 100:.4f}%"
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        np.savez(
            path,
            user_idx=self.user_idx,
            item_idx=self.item_idx,
            rating_half=(self.rating * RATING_SCALE).astype(np.uint8),
            timestamp=self.timestamp,
            user_ids=self.user_ids,
            item_ids=self.item_ids,
        )
        size_mb = os.path.getsize(path) / (1024 * 1024)
        logger.info("Saved interaction artifact to %s (%.0f MB)", path, size_mb)

    @classmethod
    def load(cls, path: str) -> "Interactions":
        with np.load(path) as z:
            return cls(
                user_idx=z["user_idx"],
                item_idx=z["item_idx"],
                rating=z["rating_half"].astype(np.float32) / RATING_SCALE,
                timestamp=z["timestamp"],
                user_ids=z["user_ids"],
                item_ids=z["item_ids"],
            )

    def to_csr(
        self,
        weighting: str = "confidence",
        alpha: float = 18.0,
        positive_only: bool = True,
    ) -> csr_matrix:
        """Builds the user x item matrix used for collaborative training.

        ``weighting`` selects how an explicit star rating becomes an implicit
        preference weight:

        ``confidence``
            The Hu/Koren/Volinsky formulation adapted to graded feedback. A rating
            is mapped to a preference in [0, 1] via its distance above the
            positive threshold, then scaled by ``alpha``. A 5.0 therefore carries
            far more confidence than a 3.5, while ratings below the threshold are
            dropped (they are evidence of *dislike*, not of interest).
        ``binary``
            Every positive interaction gets weight 1. Used as an ablation
            baseline in evaluation.
        """
        rating = self.rating
        if positive_only:
            keep = rating >= POSITIVE_THRESHOLD
            rows = self.user_idx[keep]
            cols = self.item_idx[keep]
            rating = rating[keep]
        else:
            rows = self.user_idx
            cols = self.item_idx

        if weighting == "binary":
            data = np.ones(rating.shape[0], dtype=np.float32)
        elif weighting == "confidence":
            # Graded preference in (0, 1]: 3.5 -> 0.33, 4.0 -> 0.55, 5.0 -> 1.0
            graded = (rating - POSITIVE_THRESHOLD) / (5.0 - POSITIVE_THRESHOLD)
            preference = (0.33 + 0.67 * graded).astype(np.float32)
            data = (alpha * preference).astype(np.float32)
        else:
            raise ValueError(f"Unknown weighting: {weighting!r}")

        matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(self.n_users, self.n_items),
            dtype=np.float32,
        )
        matrix.sum_duplicates()
        return matrix


def _read_ratings_csv(path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Reads ratings.csv into narrow numpy arrays via Arrow's threaded CSV reader."""
    import pyarrow.csv as pv

    logger.info("Reading %s ...", path)
    table = pv.read_csv(
        path,
        convert_options=pv.ConvertOptions(
            column_types={
                "userId": "uint32",
                "movieId": "uint32",
                "rating": "float32",
                "timestamp": "int64",
            }
        ),
    )
    users = table["userId"].to_numpy()
    items = table["movieId"].to_numpy()
    ratings = table["rating"].to_numpy()
    stamps = table["timestamp"].to_numpy().astype(np.uint32)
    logger.info("Read %s rating rows", f"{table.num_rows:,}")
    return users, items, ratings, stamps


def build_from_movielens(
    ratings_csv: str,
    out_path: Optional[str] = None,
    min_item_ratings: int = 5,
    min_user_ratings: int = 5,
    max_user_ratings: int = 2000,
    seed: int = 20260917,
) -> Interactions:
    """Builds and caches the compacted interaction artifact.

    Filtering rationale:

    * ``min_item_ratings`` -- items with a handful of ratings contribute noise to
      the latent space and can never be evaluated reliably. At 5 this retains
      ~44k of 83k rated titles while dropping only ~0.3% of interactions.
    * ``min_user_ratings`` -- users below this cannot be split into
      fit/holdout halves for the strong-generalisation evaluation protocol.
    * ``max_user_ratings`` -- a few thousand power users have 10k+ ratings each
      and would dominate the item factors. Their histories are subsampled to the
      most recent ``max_user_ratings`` entries, which preserves their taste while
      bounding their influence.
    """
    users, items, ratings, stamps = _read_ratings_csv(ratings_csv)

    # --- Iterative core filtering -------------------------------------------------
    # Dropping sparse items can push users below their threshold and vice versa,
    # so alternate until the surviving set is stable.
    keep = np.ones(users.shape[0], dtype=bool)
    for iteration in range(6):
        item_counts = np.bincount(items[keep], minlength=int(items.max()) + 1)
        item_ok = item_counts >= min_item_ratings
        keep &= item_ok[items]

        user_counts = np.bincount(users[keep], minlength=int(users.max()) + 1)
        user_ok = user_counts >= min_user_ratings
        new_keep = keep & user_ok[users]

        if new_keep.sum() == keep.sum():
            keep = new_keep
            break
        keep = new_keep
        logger.info("  core filter pass %d -> %s interactions", iteration + 1, f"{int(keep.sum()):,}")

    users, items, ratings, stamps = users[keep], items[keep], ratings[keep], stamps[keep]

    # --- Subsample power users ----------------------------------------------------
    user_counts = np.bincount(users, minlength=int(users.max()) + 1)
    heavy = np.where(user_counts > max_user_ratings)[0]
    if heavy.size:
        rng = np.random.default_rng(seed)
        # Sort by (user, timestamp) so each user's slice is chronological.
        order = np.lexsort((stamps, users))
        users, items, ratings, stamps = users[order], items[order], ratings[order], stamps[order]

        boundaries = np.flatnonzero(np.diff(users)) + 1
        starts = np.concatenate(([0], boundaries))
        ends = np.concatenate((boundaries, [users.shape[0]]))

        drop = np.zeros(users.shape[0], dtype=bool)
        heavy_set = set(heavy.tolist())
        for start, end in zip(starts, ends):
            if int(users[start]) not in heavy_set:
                continue
            # Keep the most recent max_user_ratings entries.
            drop[start : end - max_user_ratings] = True
        kept = ~drop
        logger.info(
            "Subsampled %s power users: dropped %s interactions",
            f"{heavy.size:,}",
            f"{int(drop.sum()):,}",
        )
        users, items, ratings, stamps = users[kept], items[kept], ratings[kept], stamps[kept]
        del drop, kept
        _ = rng

    # --- Reindex to contiguous matrix coordinates ---------------------------------
    user_ids, user_idx = np.unique(users, return_inverse=True)
    item_ids, item_idx = np.unique(items, return_inverse=True)

    interactions = Interactions(
        user_idx=user_idx.astype(np.uint32),
        item_idx=item_idx.astype(np.uint32),
        rating=ratings.astype(np.float32),
        timestamp=stamps.astype(np.uint32),
        user_ids=user_ids.astype(np.int32),
        item_ids=item_ids.astype(np.int32),
    )
    logger.info("Built interaction set: %s", interactions.describe())

    if out_path:
        interactions.save(out_path)
    return interactions


def compute_movie_stats(ratings_csv: str, half_life_years: float = 2.5) -> "pd.DataFrame":
    """Aggregates per-movie rating statistics straight from the CSV.

    Produces the columns the catalogue needs for ranking and display:

    ``rating_count`` / ``rating_mean``
        Raw MovieLens volume and average.
    ``bayes_score``
        A shrunk average (the IMDb weighted-rating form) so a title with four
        5-star ratings does not outrank a classic with 80,000. ``m`` is set to
        the 80th percentile of rating counts, ``C`` to the global mean.
    ``ml_trending``
        Exponentially time-decayed rating volume. Note MovieLens stops in mid
        2023, so this measures *historical* momentum only; the live trending
        signal is rebuilt from TMDB popularity after enrichment.
    """
    import pandas as pd

    users, items, ratings, stamps = _read_ratings_csv(ratings_csv)
    del users

    n_slots = int(items.max()) + 1
    count = np.bincount(items, minlength=n_slots).astype(np.float64)
    total = np.bincount(items, weights=ratings.astype(np.float64), minlength=n_slots)

    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, total / np.maximum(count, 1), 0.0)

    global_mean = float(ratings.mean())
    m = float(np.percentile(count[count > 0], 80))
    bayes = (count * mean + m * global_mean) / (count + m)
    bayes = np.where(count > 0, bayes, 0.0)

    # Time-decayed volume, anchored on the newest rating in the archive.
    newest = float(stamps.max())
    age_years = (newest - stamps.astype(np.float64)) / (365.25 * 24 * 3600)
    decay = np.exp2(-age_years / half_life_years)
    decayed = np.bincount(items, weights=decay, minlength=n_slots)

    movie_ids = np.flatnonzero(count > 0)
    frame = pd.DataFrame(
        {
            "movieId": movie_ids.astype(np.int64),
            "rating_count": count[movie_ids].astype(np.int64),
            "rating_mean": np.round(mean[movie_ids], 4),
            "bayes_score": np.round(bayes[movie_ids], 4),
            "ml_trending": np.round(decayed[movie_ids], 4),
        }
    )
    logger.info(
        "Aggregated stats for %s movies (global mean %.3f, shrink m=%.0f)",
        f"{len(frame):,}",
        global_mean,
        m,
    )
    return frame
