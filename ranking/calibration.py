"""Evidence that the score can be trusted: reliability, scores and optional recalibration."""

from __future__ import annotations

import numpy as np
import pandas as pd


def reliability_table(p: np.ndarray, y: np.ndarray, min_bin: int = 100) -> pd.DataFrame:
    """Decile table with announced mean, observed mean and count; small bins are merged. Step 4."""
    raise NotImplementedError("DG-19 step 4")


def brier(p: np.ndarray, y: np.ndarray) -> float:
    raise NotImplementedError("DG-19 step 4")


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    raise NotImplementedError("DG-19 step 4")


def auc(p: np.ndarray, y: np.ndarray) -> float:
    """Area under the ROC curve with average ranks for ties. Step 4."""
    raise NotImplementedError("DG-19 step 4")


def isotonic_fit(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pool-adjacent-violators fit; returns the thresholds and fitted values. Step 4."""
    raise NotImplementedError("DG-19 step 4")


def isotonic_apply(thresholds: np.ndarray, values: np.ndarray, p: np.ndarray) -> np.ndarray:
    raise NotImplementedError("DG-19 step 4")
