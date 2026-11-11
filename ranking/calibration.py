"""Evidence that the score can be trusted: reliability, scores and optional recalibration."""

from __future__ import annotations

import numpy as np
import pandas as pd

LOG_LOSS_EPS = 1e-6  # probabilities are clipped to [eps, 1 - eps] before taking logarithms


def _as_vectors(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return p and y as float vectors of the same non-zero length."""
    p_arr, y_arr = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    if p_arr.shape != y_arr.shape or p_arr.ndim != 1 or p_arr.size == 0:
        raise ValueError("p and y must be non-empty vectors of the same length")
    return p_arr, y_arr


def reliability_table(p: np.ndarray, y: np.ndarray, min_bin: int = 100) -> pd.DataFrame:
    """Decile table with announced mean, observed mean and count; small bins are merged.

    Columns: p_low, p_high (range of the announced scores in the bin), n, announced, observed and
    gap (announced - observed). Empty deciles are dropped, then any bin with fewer than `min_bin`
    units is merged into its smaller neighbour until none is left (or only one bin remains).
    """
    p_arr, y_arr = _as_vectors(p, y)
    decile = np.minimum((p_arr * 10).astype(int), 9)  # 1.0 falls in the last decile
    bins = [
        [int(mask.sum()), float(p_arr[mask].sum()), float(y_arr[mask].sum()), p_arr[mask].min(),
         p_arr[mask].max()]
        for d in range(10)
        if (mask := decile == d).any()
    ]  # fmt: skip
    while len(bins) > 1 and min(b[0] for b in bins) < min_bin:
        i = min(range(len(bins)), key=lambda k: bins[k][0])
        neighbours = [k for k in (i - 1, i + 1) if 0 <= k < len(bins)]
        j = min(neighbours, key=lambda k: bins[k][0])
        lo, hi = min(i, j), max(i, j)
        merged = [
            bins[lo][0] + bins[hi][0],
            bins[lo][1] + bins[hi][1],
            bins[lo][2] + bins[hi][2],
            bins[lo][3],
            bins[hi][4],
        ]
        bins[lo : hi + 1] = [merged]
    table = pd.DataFrame(bins, columns=["n", "sum_p", "sum_y", "p_low", "p_high"])
    table["announced"] = table["sum_p"] / table["n"]
    table["observed"] = table["sum_y"] / table["n"]
    table["gap"] = table["announced"] - table["observed"]
    return table[["p_low", "p_high", "n", "announced", "observed", "gap"]]


def calibration_gap(p: np.ndarray, y: np.ndarray) -> float:
    """Mean |announced - observed| over the ten equal-width deciles, weighted by their size."""
    p_arr, y_arr = _as_vectors(p, y)
    decile = np.minimum((p_arr * 10).astype(int), 9)
    total = 0.0
    for d in range(10):
        mask = decile == d
        if mask.any():
            total += mask.sum() * abs(p_arr[mask].mean() - y_arr[mask].mean())
    return float(total / p_arr.size)


def brier(p: np.ndarray, y: np.ndarray) -> float:
    """Mean squared difference between the announced score and the 0/1 outcome."""
    p_arr, y_arr = _as_vectors(p, y)
    return float(np.mean((p_arr - y_arr) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    """Mean negative log-likelihood of the outcomes, scores clipped away from 0 and 1."""
    p_arr, y_arr = _as_vectors(p, y)
    clipped = np.clip(p_arr, LOG_LOSS_EPS, 1.0 - LOG_LOSS_EPS)
    return float(-np.mean(y_arr * np.log(clipped) + (1.0 - y_arr) * np.log(1.0 - clipped)))


def auc(p: np.ndarray, y: np.ndarray) -> float:
    """Area under the ROC curve with average ranks for ties; NaN if only one outcome occurs."""
    p_arr, y_arr = _as_vectors(p, y)
    positives = int((y_arr == 1).sum())
    negatives = y_arr.size - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(p_arr).rank(method="average").to_numpy()
    return float(
        (ranks[y_arr == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives)
    )


def isotonic_fit(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pool-adjacent-violators fit; returns the thresholds and fitted values.

    The fit is non-decreasing in p. `thresholds` are the mean score of each pooled block and
    `values` the observed rate in it; apply with `isotonic_apply`.
    """
    p_arr, y_arr = _as_vectors(p, y)
    order = np.argsort(p_arr, kind="stable")
    blocks: list[list[float]] = []  # [sum of p, sum of y, count]
    for score, outcome in zip(p_arr[order], y_arr[order], strict=True):
        blocks.append([score, outcome, 1.0])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] >= blocks[-1][1] / blocks[-1][2]:
            last = blocks.pop()
            for k in range(3):
                blocks[-1][k] += last[k]
    thresholds = np.array([b[0] / b[2] for b in blocks])
    values = np.array([b[1] / b[2] for b in blocks])
    return thresholds, values


def isotonic_apply(thresholds: np.ndarray, values: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Recalibrated scores: linear interpolation of the fitted steps, flat beyond the ends."""
    return np.interp(np.asarray(p, dtype=float), thresholds, values)
