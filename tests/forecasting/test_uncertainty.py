import pandas as pd
import pytest

from forecasting.uncertainty import calibrate, coverage, upper_bound


def test_upper_bound_is_nonnegative_and_covers_calibration_fixture():
    frame = pd.DataFrame({"candidate": [0.0, 1.0, 4.0], "actual": [0.0, 2.0, 7.0]})
    multiplier = calibrate(frame, level=0.9, scale_offset=1.0)
    bound = upper_bound(frame["candidate"], multiplier, 1.0)
    assert (bound >= 0).all()
    assert coverage(frame["actual"], bound)["rate"] == 1.0


def test_calibration_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        calibrate(pd.DataFrame(), level=0.9, scale_offset=1.0)
    with pytest.raises(ValueError):
        upper_bound(pd.Series([-1.0]), 0.0, 1.0)
