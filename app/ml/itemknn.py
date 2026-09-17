"""Shrunk item-item cosine neighbourhood model.

Latent factorisation is good at generalising but bad at explaining: a 128-dim
embedding cannot say *why* a title was suggested. A neighbourhood model can, and
on MovieLens-scale data it also stays competitive on accuracy, so it serves three
purposes here:

* a fusion signal alongside iALS, strongest exactly where iALS is weakest (users
  with very short histories);
* the "because you watched X" attribution, which is a direct read-out of which
  neighbour contributed most to a score;
* the "more like this" row on the detail page.

Two details matter for quality:

**Shrinkage.** Raw cosine over sparse co-occurrence is dominated by coincidence:
two obscure titles sharing their only two viewers score 1.0. Damping by
co-occurrence support, ``sim * n / (n + h)``, pushes those to near zero while
leaving well-supported pairs untouched.

**Popularity discounting.** Normalising item vectors by ``||x||^alpha`` with
alpha below 1 keeps blockbusters from being everyone's nearest neighbour, which is
what otherwise makes neighbourhood recommendations collapse onto the top 100
titles.
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import Optional, Sequence

import numpy as np
from scipy.sparse import csr_matrix, diags

logger = logging.getLogger(__name__)

# Items scored per block. Each block materialises (block x n_items) floats.
_BLOCK = 512


class ItemKNN:
    """Top-K pruned item-item similarity over implicit feedback."""

    def __init__(
        self,
        top_k: int = 200,
        shrinkage: float = 60.0,
        popularity_damping: float = 0.55,
    ):
        self.top_k = top_k
        self.shrinkage = shrinkage
        self.popularity_damping = popularity_damping

        self.similarity: Optional[csr_matrix] = None
        self.item_ids: Optional[np.ndarray] = None
        self._item_id_to_index: Optional[dict[int, int]] = None

    def fit(self, matrix: csr_matrix, item_ids: Optional[np.ndarray] = None) -> "ItemKNN":
        n_items = matrix.shape[1]
        self.item_ids = item_ids if item_ids is not None else np.arange(n_items, dtype=np.int32)
        self._item_id_to_index = None

        # Binary presence drives the neighbourhood; graded confidence would let a
        # handful of 5-star ratings dominate the co-occurrence counts.
        presence = matrix.copy()
        presence.data = np.ones_like(presence.data, dtype=np.float32)
        presence = presence.tocsc()

        support = np.asarray(presence.sum(axis=0)).ravel()
        # Damped inverse norm: alpha=1 is plain cosine, alpha=0 leaves raw counts.
        norms = np.power(np.maximum(support, 1.0), self.popularity_damping, dtype=np.float32)
        normalised = (presence @ diags(1.0 / norms)).tocsc()

        logger.info(
            "Building item-item neighbourhood: %s items, top-%d, shrinkage %.0f",
            f"{n_items:,}", self.top_k, self.shrinkage,
        )

        rows: list[np.ndarray] = []
        cols: list[np.ndarray] = []
        values: list[np.ndarray] = []

        presence_csc = presence
        for start in range(0, n_items, _BLOCK):
            end = min(start + _BLOCK, n_items)
            block = normalised[:, start:end]

            # Similarity of every catalogue item against this block.
            scores = np.asarray((block.T @ normalised).todense(), dtype=np.float32)
            # Co-occurrence support for the same pairs, for the shrink term.
            cooccurrence = np.asarray(
                (presence_csc[:, start:end].T @ presence_csc).todense(), dtype=np.float32
            )
            scores *= cooccurrence / (cooccurrence + self.shrinkage)

            # An item is always its own nearest neighbour; drop the diagonal.
            scores[np.arange(end - start), np.arange(start, end)] = 0.0

            keep = min(self.top_k, n_items - 1)
            top_idx = np.argpartition(-scores, keep - 1, axis=1)[:, :keep]
            top_val = np.take_along_axis(scores, top_idx, axis=1)

            nonzero = top_val > 1e-6
            local_rows = np.repeat(np.arange(start, end), nonzero.sum(axis=1))
            rows.append(local_rows)
            cols.append(top_idx[nonzero])
            values.append(top_val[nonzero])

            if (start // _BLOCK) % 20 == 0:
                logger.info("  %s/%s items", f"{end:,}", f"{n_items:,}")

        self.similarity = csr_matrix(
            (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
            shape=(n_items, n_items),
            dtype=np.float32,
        )
        logger.info(
            "Neighbourhood built: %s stored similarities (%.1f per item)",
            f"{self.similarity.nnz:,}", self.similarity.nnz / max(n_items, 1),
        )
        return self

    # ------------------------------------------------------------------- serving

    def score(self, item_indices: Sequence[int], weights: Sequence[float]) -> np.ndarray:
        """Aggregates neighbour similarity across a user's profile."""
        if self.similarity is None:
            raise RuntimeError("Model is not trained or loaded.")
        item_indices = np.asarray(item_indices, dtype=np.int64)
        if item_indices.size == 0:
            return np.zeros(self.similarity.shape[0], dtype=np.float32)
        weight_vector = np.asarray(weights, dtype=np.float32)
        return np.asarray(self.similarity[item_indices].T @ weight_vector, dtype=np.float32).ravel()

    def top_contributors(
        self,
        target_index: int,
        profile_indices: Sequence[int],
        limit: int = 3,
    ) -> list[tuple[int, float]]:
        """Which profile items pushed ``target_index`` up, strongest first.

        This is the explanation primitive: the returned profile indices are the
        titles that actually drove the recommendation, not a post-hoc guess.
        """
        if self.similarity is None:
            raise RuntimeError("Model is not trained or loaded.")
        profile_indices = np.asarray(profile_indices, dtype=np.int64)
        if profile_indices.size == 0:
            return []

        row = self.similarity[target_index]
        dense = np.zeros(self.similarity.shape[0], dtype=np.float32)
        dense[row.indices] = row.data
        contributions = dense[profile_indices]

        order = np.argsort(-contributions)[:limit]
        return [
            (int(profile_indices[i]), float(contributions[i]))
            for i in order
            if contributions[i] > 1e-6
        ]

    def similar_items(self, item_index: int, limit: int = 12) -> list[tuple[int, float]]:
        """Nearest neighbours of a single item."""
        if self.similarity is None:
            raise RuntimeError("Model is not trained or loaded.")
        row = self.similarity[item_index]
        if row.nnz == 0:
            return []
        order = np.argsort(-row.data)[:limit]
        return [(int(row.indices[i]), float(row.data[i])) for i in order]

    def item_id_to_index(self) -> dict[int, int]:
        if self._item_id_to_index is None:
            self._item_id_to_index = {int(mid): i for i, mid in enumerate(self.item_ids)}
        return self._item_id_to_index

    # --------------------------------------------------------------- persistence

    def save(self, directory: str, name: str = "itemknn.pkl") -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "wb") as handle:
            pickle.dump(
                {
                    "top_k": self.top_k,
                    "shrinkage": self.shrinkage,
                    "popularity_damping": self.popularity_damping,
                    "similarity": self.similarity,
                    "item_ids": self.item_ids,
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info("Saved item neighbourhood to %s", path)
        return path

    @classmethod
    def load(cls, directory: str, name: str = "itemknn.pkl") -> "ItemKNN":
        with open(os.path.join(directory, name), "rb") as handle:
            state = pickle.load(handle)
        model = cls(
            top_k=state["top_k"],
            shrinkage=state["shrinkage"],
            popularity_damping=state["popularity_damping"],
        )
        model.similarity = state["similarity"]
        model.item_ids = state["item_ids"]
        return model
