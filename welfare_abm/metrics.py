from __future__ import annotations

import numpy as np


def gini(values: list[float] | np.ndarray) -> float:
    """Return the Gini coefficient for non-negative shifted values."""

    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    min_value = arr.min()
    if min_value < 0:
        arr = arr - min_value
    if np.allclose(arr.sum(), 0):
        return 0.0
    arr = np.sort(arr)
    n = arr.size
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * arr) / (n * np.sum(arr))) - ((n + 1) / n))


def safe_mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0

