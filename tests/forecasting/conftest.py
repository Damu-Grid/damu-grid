"""Tiny in-memory fixtures. Tests never depend on the full official CSVs."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def facilities() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "facility_id": ["HSP-001", "HSP-002", "RBTC-NBO", "SAT-NYR"],
            "facility_type": [
                "national_referral",
                "county_hospital",
                "regional_blood_centre",
                "satellite_blood_centre",
            ],
        }
    )


@pytest.fixture
def requests_frame() -> pd.DataFrame:
    rows = [
        # (facility_id, requested_at, group, component, units)
        ("HSP-001", "2026-01-05 10:00", "O+", "RBC", 2),
        ("HSP-001", "2026-01-05 15:00", "O+", "RBC", 1),
        ("HSP-001", "2026-01-06 09:00", "A+", "RBC", 4),
        ("HSP-002", "2026-01-06 09:00", "O+", "RBC", 3),
        ("HSP-001", "2026-01-06 11:00", "unknown", "RBC", 5),  # excluded: unknown group
        ("HSP-001", "2026-01-06 12:00", "O+", "PLT", 6),  # excluded: other component
        ("RBTC-NBO", "2026-01-06 13:00", "O+", "RBC", 7),  # excluded: not a hospital
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "facility_id",
            "requested_at",
            "patient_blood_group",
            "component_requested",
            "units_requested",
        ],
    )
    frame["requested_at"] = pd.to_datetime(frame["requested_at"])
    frame["request_id"] = [f"R{i}" for i in range(len(frame))]
    return frame
