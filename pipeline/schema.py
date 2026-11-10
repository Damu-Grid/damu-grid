"""Official CSV contracts, taken from data/raw/DATA_DICTIONARY.md and docs/DATA.md.

Column names are the official ones. Types are what the dictionary describes; a value that
cannot be parsed as its declared type makes validation fail instead of silently becoming NaN.
"""

from __future__ import annotations

# Column kinds: str, int, float, bool, date, datetime
TABLES: dict[str, dict[str, str]] = {
    "facilities": {
        "facility_id": "str", "name": "str", "facility_type": "str", "county": "str",
        "lat": "float", "lon": "float", "keph_level": "str", "beds": "int",
        "grid_reliability": "float", "connectivity": "str", "supply_centre_id": "str",
        "makes_platelets": "bool", "separates_components": "bool",
        "has_blood_fridge_backup_power": "bool", "routine_deliveries_per_week": "int",
    },
    "routes": {
        "from_facility_id": "str", "to_facility_id": "str", "road_km": "float",
        "typical_travel_hours": "float", "road_quality": "str",
    },
    "donors": {
        "donor_id": "str", "sex": "str", "birth_date": "date", "blood_group": "str",
        "home_county": "str", "donor_category": "str", "registration_date": "date",
        "registration_site_id": "str", "preferred_channel": "str", "consent_to_contact": "bool",
        "phone_last4": "str",
    },
    "drives": {
        "drive_id": "str", "date": "date", "collecting_site_id": "str", "county": "str",
        "venue_type": "str", "registered_donors": "int", "donations_collected": "int",
        "donors_deferred": "int",
    },
    "donations": {
        "donation_id": "str", "donor_id": "str", "drive_id": "str", "collection_date": "date",
        "collecting_site_id": "str", "outcome": "str", "deferral_reason": "str",
        "volume_ml": "float", "screening_result": "str", "tti_marker": "str", "tested_date": "date",
    },
    "units": {
        "unit_id": "str", "donation_id": "str", "component": "str", "blood_group": "str",
        "collection_date": "date", "expiry_date": "date", "processed_at_id": "str",
        "current_facility_id": "str", "status": "str", "status_date": "date",
        "temp_excursion_exposed": "bool", "issued_request_id": "str", "opening_stock": "bool",
    },
    "transfers": {
        "transfer_id": "str", "unit_id": "str", "from_facility_id": "str", "to_facility_id": "str",
        "transfer_type": "str", "request_id": "str", "dispatched_at": "datetime",
        "received_at": "datetime", "transport_mode": "str", "coolbox_max_temp_c": "float",
    },
    "requests": {
        "request_id": "str", "facility_id": "str", "facility_name_raw": "str",
        "requested_at": "datetime", "clinical_indication": "str", "patient_sex": "str",
        "patient_age_band": "str", "patient_blood_group": "str", "component_requested": "str",
        "units_requested": "int", "urgency": "str", "units_issued": "int",
        "units_issued_group_substituted": "int", "units_from_local_stock": "int",
        "emergency_supplied_from_id": "str", "last_unit_available_at": "datetime", "outcome": "str",
    },
    "daily_stock": {
        "date": "date", "facility_id": "str", "component": "str", "blood_group": "str",
        "units_in_stock_end_of_day": "int",
    },
    "power_outages": {
        "outage_id": "str", "facility_id": "str", "start_time": "datetime", "end_time": "datetime",
        "duration_hours": "float", "backup_power_engaged": "bool",
    },
    "temperature_logs": {
        "facility_id": "str", "recorded_at": "datetime", "temp_c": "float",
    },
}

# Primary keys we rely on (must be unique and non-empty).
PRIMARY_KEYS: dict[str, list[str]] = {
    "facilities": ["facility_id"],
    "routes": ["from_facility_id", "to_facility_id"],
    "donors": ["donor_id"],
    "drives": ["drive_id"],
    "donations": ["donation_id"],
    "units": ["unit_id"],
    "transfers": ["transfer_id"],
    "requests": ["request_id"],
    "daily_stock": ["date", "facility_id", "component", "blood_group"],
    "power_outages": ["outage_id"],
}

# Row counts measured on the official CSVs (docs/DATA.md, excluding header).
EXPECTED_ROWS: dict[str, int] = {
    "facilities": 47, "routes": 2162, "donors": 43363, "drives": 1091, "donations": 47363,
    "units": 49426, "transfers": 35181, "requests": 17430, "daily_stock": 185785,
    "power_outages": 2609, "temperature_logs": 399280,
}

# Columns that must reference facilities.facility_id when filled.
FACILITY_KEYS: dict[str, list[str]] = {
    "facilities": ["supply_centre_id"],
    "routes": ["from_facility_id", "to_facility_id"],
    "donors": ["registration_site_id"],
    "drives": ["collecting_site_id"],
    "donations": ["collecting_site_id"],
    "units": ["processed_at_id", "current_facility_id"],
    "transfers": ["from_facility_id", "to_facility_id"],
    "requests": ["facility_id", "emergency_supplied_from_id"],
    "daily_stock": ["facility_id"],
    "power_outages": ["facility_id"],
    "temperature_logs": ["facility_id"],
}

BLOOD_GROUPS = ("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-")
COMPONENTS = ("RBC", "WB", "PLT", "FFP", "CRYO")

# Allowed values for categorical columns (data dictionary). NA is allowed unless the column is a key.
ENUMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("units", "component"): COMPONENTS,
    ("units", "blood_group"): BLOOD_GROUPS,
    ("units", "status"): ("in_stock", "transfused", "expired", "discarded_temperature"),
    ("daily_stock", "component"): COMPONENTS,
    ("daily_stock", "blood_group"): BLOOD_GROUPS,
    ("requests", "patient_blood_group"): BLOOD_GROUPS + ("unknown",),
    ("requests", "component_requested"): ("RBC", "PLT", "FFP"),
    ("requests", "urgency"): ("emergency", "urgent", "routine"),
    ("requests", "outcome"): ("fulfilled", "partially_fulfilled", "not_fulfilled", "deferred_to_later"),
    ("transfers", "transfer_type"): (
        "routine", "emergency_request", "emergency_cross_region", "inter_centre_rebalancing"),
    ("facilities", "connectivity"): ("4G", "3G", "2G"),
    ("donors", "blood_group"): BLOOD_GROUPS,
    ("routes", "road_quality"): ("good", "fair", "poor"),
}

# Facility types that receive hospital demand (docs/DATA.md, ADR-005): 32 sites.
HOSPITAL_TYPES = (
    "national_referral", "county_referral", "county_hospital", "sub_county_hospital",
    "maternity_hospital", "mission_hospital", "private_hospital",
)
