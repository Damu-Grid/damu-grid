"""Non-negative, one-sided demand upper bound calibrated on earlier origins."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def calibrate(calibration: pd.DataFrame, level: float, scale_offset: float) -> float:
    if not 0 < level < 1 or scale_offset <= 0 or calibration.empty:
        raise ValueError("Valid level, positive offset, and calibration rows required")
    predictions = calibration["candidate"].to_numpy(dtype=float)
    actual = calibration["actual"].to_numpy(dtype=float)
    scores = np.maximum(0, actual - predictions) / np.sqrt(predictions + scale_offset)
    rank = min(len(scores), math.ceil((len(scores) + 1) * level)) - 1
    return float(np.sort(scores)[rank])


def upper_bound(predicted: pd.Series, multiplier: float, scale_offset: float) -> pd.Series:
    if multiplier < 0 or scale_offset <= 0 or (predicted < 0).any():
        raise ValueError("Non-negative predictions and multiplier required")
    return (predicted + multiplier * np.sqrt(predicted + scale_offset)).clip(lower=0)


def coverage(actual: pd.Series, upper: pd.Series) -> dict:
    if len(actual) != len(upper) or actual.empty:
        raise ValueError("Aligned, nonempty series required")
    return {"covered": int((actual <= upper).sum()), "n": int(len(actual)),
            "rate": float((actual <= upper).mean())}
