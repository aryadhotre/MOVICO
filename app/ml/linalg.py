"""Small linear-algebra helpers, kept free of scikit-learn.

scikit-learn costs 84 MB of resident memory purely to import, and the serving
path used exactly one function from it: ``sklearn.preprocessing.normalize``. On a
512 MB instance that import is the difference between fitting and being killed,
so the handful of lines it was providing live here instead.

scikit-learn is still used for fitting the TF-IDF channels, but that happens
offline in the training pipeline and never in the API process.
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix, issparse


def row_normalize(matrix):
    """Scales every row to unit L2 norm, in place where possible.

    Accepts a dense array or any scipy sparse matrix. Zero rows are left as zero
    rather than producing NaN, which is what ``normalize`` does and what callers
    here rely on for items with no features.
    """
    if issparse(matrix):
        matrix = csr_matrix(matrix, copy=True)
        # Squaring the stored values and summing per row gives the row norms
        # without densifying anything.
        squared = matrix.copy()
        squared.data **= 2
        norms = np.sqrt(np.asarray(squared.sum(axis=1)).ravel())
        norms[norms == 0] = 1.0
        # Repeat each row's norm across its stored entries and divide once.
        repeats = np.diff(matrix.indptr)
        matrix.data /= np.repeat(norms, repeats)
        return matrix

    array = np.asarray(matrix, dtype=np.float32)
    if array.ndim == 1:
        norm = float(np.sqrt(array @ array))
        return array if norm == 0 else array / norm

    norms = np.sqrt((array * array).sum(axis=1, keepdims=True))
    norms[norms == 0] = 1.0
    return array / norms
