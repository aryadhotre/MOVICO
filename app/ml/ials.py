"""Implicit ALS with a conjugate-gradient inner solver.

Implements the Hu/Koren/Volinsky implicit-feedback matrix factorisation, with two
refinements that matter a great deal in practice:

1. **Conjugate-gradient inner solve** (Takacs, Pilaszy & Tikk, 2011). The exact
   ridge solve costs ``O(f^3 + n_u f^2)`` per user. Because the system is
   symmetric positive definite and ALS only needs an *approximate* step to keep
   descending, three CG iterations reach essentially the same solution at
   ``O(n_u f)`` per step. At f=128 this is the difference between hours and
   minutes over 33M interactions.

2. **Frequency-scaled regularisation** (Rendle et al., 2022, "Revisiting the
   Performance of iALS"). Penalising every embedding equally over-regularises
   users with long histories and under-regularises the tail. Scaling the penalty
   by ``(count + 1) ** nu`` closes most of the reported gap to far more
   expensive models.

The Gramian trick is what makes implicit ALS tractable at all: the loss sums over
*every* user-item pair, but

    Y^T C_u Y = Y^T Y + Y_u^T (C_u - I) Y_u

so the dense term ``Y^T Y`` is computed once per half-iteration and shared by all
users, leaving only the observed entries to be touched per user.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from typing import Optional, Sequence

import numpy as np
from scipy.sparse import csr_matrix

logger = logging.getLogger(__name__)


# Rows of the interaction matrix processed per sampled-product chunk. Each chunk
# materialises two (chunk x factors) gathers, so this bounds peak scratch memory.
_SDDMM_CHUNK = 500_000


class _RidgeSystem:
    """The batched normal-equation operator for one half of an ALS iteration.

    Every row of the factor matrix has its own linear system, but they all share
    the dense Gramian ``Y^T Y``. Solving them one at a time in Python spends
    almost all of its time on interpreter and numpy dispatch overhead, because an
    average profile touches only a few dozen items. Instead the whole batch is
    advanced together, which turns the solve into four BLAS/sparse kernels:

    ``P @ YtY``
        dense GEMM, multithreaded.
    ``s = rowwise_dot(P[rows], Y[cols])``
        a sampled dense-dense product over the sparsity pattern, chunked to bound
        scratch memory.
    ``T @ Y``
        sparse-dense GEMM that scatter-accumulates the per-item contributions.

    Cost is ``O(nnz * f)`` per operator application with no Python-level loop over
    rows, which is what makes 33M interactions trainable in minutes.
    """

    def __init__(
        self,
        matrix: csr_matrix,
        regularization: float,
        reg_exponent: float,
    ):
        self.indptr = matrix.indptr
        self.indices = matrix.indices
        self.confidence = matrix.data.astype(np.float32, copy=False)
        self.n_rows = matrix.shape[0]

        counts = np.diff(self.indptr)
        # Row index for each stored entry, needed by the sampled product.
        self.rows = np.repeat(np.arange(self.n_rows, dtype=np.int64), counts)
        # (C_u - I): only the confidence in excess of the implicit unit weight.
        self.confidence_excess = self.confidence - 1.0
        # Per-row ridge penalty, scaled by profile length.
        self.lam = (regularization * np.maximum(counts, 1) ** reg_exponent).astype(np.float32)
        self.empty = counts == 0

    def _sampled_product(self, P: np.ndarray, Y: np.ndarray) -> np.ndarray:
        """Computes ``dot(P[u], Y[i])`` for every stored (u, i) entry."""
        out = np.empty(self.rows.shape[0], dtype=np.float32)
        for start in range(0, self.rows.shape[0], _SDDMM_CHUNK):
            end = min(start + _SDDMM_CHUNK, self.rows.shape[0])
            np.einsum(
                "ij,ij->i",
                P[self.rows[start:end]],
                Y[self.indices[start:end]],
                out=out[start:end],
            )
        return out

    def rhs(self, Y: np.ndarray) -> np.ndarray:
        """``b_u = Y_u^T c_u`` for every row, as one sparse-dense product."""
        weights = csr_matrix(
            (self.confidence, self.indices, self.indptr),
            shape=(self.n_rows, Y.shape[0]),
        )
        return np.asarray(weights @ Y, dtype=np.float32)

    def apply(self, P: np.ndarray, Y: np.ndarray, YtY: np.ndarray) -> np.ndarray:
        """``A_u p_u`` for every row, where ``A_u = Y^T C_u Y + lambda_u I``."""
        scaled = self.confidence_excess * self._sampled_product(P, Y)
        spread = csr_matrix(
            (scaled, self.indices, self.indptr),
            shape=(self.n_rows, Y.shape[0]),
        )
        result = P @ YtY
        result += self.lam[:, None] * P
        result += np.asarray(spread @ Y, dtype=np.float32)
        return result

    def solve_into(self, X: np.ndarray, Y: np.ndarray, cg_steps: int) -> None:
        """Advances every row of ``X`` with a shared run of CG steps."""
        YtY = (Y.T @ Y).astype(np.float32)

        residual = self.rhs(Y) - self.apply(X, Y, YtY)
        direction = residual.copy()
        rs_old = np.einsum("ij,ij->i", residual, residual)

        for _ in range(cg_steps):
            operated = self.apply(direction, Y, YtY)
            denom = np.einsum("ij,ij->i", direction, operated)
            # Rows that have already converged (or have no data) take a zero step.
            step = np.divide(rs_old, denom, out=np.zeros_like(rs_old), where=denom > 1e-12)

            X += step[:, None] * direction
            residual -= step[:, None] * operated

            rs_new = np.einsum("ij,ij->i", residual, residual)
            beta = np.divide(rs_new, rs_old, out=np.zeros_like(rs_new), where=rs_old > 1e-12)
            direction = residual + beta[:, None] * direction
            rs_old = rs_new

        X[self.empty] = 0.0


class ImplicitALS:
    """Latent collaborative model over implicit (confidence-weighted) feedback."""

    def __init__(
        self,
        factors: int = 128,
        regularization: float = 0.06,
        reg_exponent: float = 0.7,
        iterations: int = 14,
        cg_steps: int = 3,
        seed: int = 20260917,
    ):
        self.factors = factors
        self.regularization = regularization
        self.reg_exponent = reg_exponent
        self.iterations = iterations
        self.cg_steps = cg_steps
        self.seed = seed

        self.user_factors: Optional[np.ndarray] = None
        self.item_factors: Optional[np.ndarray] = None
        self.item_ids: Optional[np.ndarray] = None
        self._item_id_to_index: Optional[dict[int, int]] = None
        self._gram_cache: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ training

    def fit(self, matrix: csr_matrix, item_ids: Optional[np.ndarray] = None) -> "ImplicitALS":
        n_users, n_items = matrix.shape
        rng = np.random.default_rng(self.seed)

        # Small random init; the scale keeps initial dot products near zero.
        self.user_factors = rng.normal(0, 0.01, (n_users, self.factors)).astype(np.float32)
        self.item_factors = rng.normal(0, 0.01, (n_items, self.factors)).astype(np.float32)
        self.item_ids = item_ids if item_ids is not None else np.arange(n_items, dtype=np.int32)
        self._item_id_to_index = None
        self._gram_cache = None

        user_csr = matrix.tocsr()
        user_system = _RidgeSystem(user_csr, self.regularization, self.reg_exponent)
        item_system = _RidgeSystem(matrix.T.tocsr(), self.regularization, self.reg_exponent)

        logger.info(
            "Training iALS: %s users x %s items, %s observations, f=%d, %d iterations",
            f"{n_users:,}",
            f"{n_items:,}",
            f"{matrix.nnz:,}",
            self.factors,
            self.iterations,
        )

        for iteration in range(self.iterations):
            started = time.time()

            user_system.solve_into(self.user_factors, self.item_factors, self.cg_steps)
            item_system.solve_into(self.item_factors, self.user_factors, self.cg_steps)

            elapsed = time.time() - started
            logger.info(
                "  iter %2d/%d  observed-RMSE %.4f  (%.1fs)",
                iteration + 1, self.iterations, self._observed_loss(user_csr), elapsed,
            )

        return self

    def _observed_loss(self, user_csr: csr_matrix, sample: int = 200_000) -> float:
        """Confidence-weighted RMSE over a sample of observed entries.

        Only a progress signal -- ranking quality is measured properly in
        ``app.ml.evaluate``.
        """
        nnz = user_csr.nnz
        if nnz == 0:
            return 0.0
        rng = np.random.default_rng(self.seed)
        picks = rng.choice(nnz, size=min(sample, nnz), replace=False)

        rows = np.searchsorted(user_csr.indptr, picks, side="right") - 1
        cols = user_csr.indices[picks]
        preds = np.einsum("ij,ij->i", self.user_factors[rows], self.item_factors[cols])
        return float(np.sqrt(np.mean((1.0 - preds) ** 2)))

    # ------------------------------------------------------------------- serving

    def fold_in(
        self,
        item_indices: Sequence[int],
        confidences: Sequence[float],
    ) -> np.ndarray:
        """Solves for a user vector given their interactions, without retraining.

        This is the serving path for real application users: they never appear in
        the training matrix, so their embedding is derived on demand from the
        frozen item factors. A single exact Cholesky solve costs ``O(f^3)`` --
        microseconds at f=128 -- so no approximation is warranted here.
        """
        if self.item_factors is None:
            raise RuntimeError("Model is not trained or loaded.")

        item_indices = np.asarray(item_indices, dtype=np.int64)
        if item_indices.size == 0:
            return np.zeros(self.factors, dtype=np.float32)

        conf = np.asarray(confidences, dtype=np.float64)
        Yu = self.item_factors[item_indices].astype(np.float64)

        lam = self.regularization * (item_indices.size ** self.reg_exponent)
        A = self._gramian() + (Yu.T * (conf - 1.0)) @ Yu
        A[np.diag_indices_from(A)] += lam
        b = Yu.T @ conf

        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            x = np.linalg.lstsq(A, b, rcond=None)[0]
        return x.astype(np.float32)

    def _gramian(self) -> np.ndarray:
        if getattr(self, "_gram_cache", None) is None:
            item_f = self.item_factors.astype(np.float64)
            self._gram_cache = item_f.T @ item_f
        return self._gram_cache.copy()

    def score_all(self, user_vector: np.ndarray) -> np.ndarray:
        """Scores every catalogue item for a (possibly folded-in) user vector."""
        return self.item_factors @ user_vector.astype(np.float32)

    def item_id_to_index(self) -> dict[int, int]:
        if self._item_id_to_index is None:
            self._item_id_to_index = {int(mid): i for i, mid in enumerate(self.item_ids)}
        return self._item_id_to_index

    # --------------------------------------------------------------- persistence

    def save(self, directory: str, name: str = "ials.pkl") -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "wb") as handle:
            pickle.dump(
                {
                    "factors": self.factors,
                    "regularization": self.regularization,
                    "reg_exponent": self.reg_exponent,
                    "iterations": self.iterations,
                    "cg_steps": self.cg_steps,
                    "item_factors": self.item_factors,
                    "item_ids": self.item_ids,
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.info("Saved iALS item factors to %s", path)
        return path

    @classmethod
    def load(cls, directory: str, name: str = "ials.pkl") -> "ImplicitALS":
        path = os.path.join(directory, name)
        with open(path, "rb") as handle:
            state = pickle.load(handle)
        model = cls(
            factors=state["factors"],
            regularization=state["regularization"],
            reg_exponent=state["reg_exponent"],
            iterations=state["iterations"],
            cg_steps=state["cg_steps"],
        )
        model.item_factors = state["item_factors"]
        model.item_ids = state["item_ids"]
        model._gram_cache = None
        return model
