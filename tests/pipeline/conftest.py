"""A tiny synthetic world written as official-format CSVs, loaded through the real loader.

Three sites: RBTC-A (centre, fridge backup), HSP-1 (hospital, no backup), HSP-2 (hospital, backup).
As-of is the default 2026-10-31 23:59:59 EAT.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pipeline.load import load_all

FACILITIES = """facility_id,name,facility_type,county,lat,lon,keph_level,beds,grid_reliability,connectivity,supply_centre_id,makes_platelets,separates_components,has_blood_fridge_backup_power,routine_deliveries_per_week
RBTC-A,Centre A,regional_blood_centre,X,-1.0,36.0,,0,0.95,4G,,True,True,True,
HSP-1,Hospital One,county_referral,X,-1.1,36.1,4,150,0.80,3G,RBTC-A,False,False,False,3
HSP-2,Hospital Two,county_hospital,Y,-1.4,36.5,4,90,0.90,2G,RBTC-A,False,False,True,2
"""

ROUTES = """from_facility_id,to_facility_id,road_km,typical_travel_hours,road_quality
RBTC-A,HSP-1,80,2.0,good
HSP-1,RBTC-A,80,2.0,good
RBTC-A,HSP-2,120,3.0,fair
HSP-2,RBTC-A,120,3.0,fair
HSP-1,HSP-2,60,1.5,poor
HSP-2,HSP-1,60,1.5,poor
"""

DONATIONS_HEADER = ("donation_id,donor_id,drive_id,collection_date,collecting_site_id,outcome,deferral_reason,"
                    "volume_ml,screening_result,tti_marker,tested_date\n")
UNITS_HEADER = ("unit_id,donation_id,component,blood_group,collection_date,expiry_date,processed_at_id,"
                "current_facility_id,status,status_date,temp_excursion_exposed,issued_request_id,opening_stock\n")

# unit, component, group, collected, expiry, site, status, status_date, exposed, tested
UNITS = [
    ("U1", "RBC", "O+", "2026-10-15", "2026-11-26", "HSP-1", "in_stock", "", "False", "2026-10-17"),
    ("U2", "RBC", "O+", "2026-10-14", "2026-11-25", "RBTC-A", "in_stock", "", "False", "2026-10-16"),
    ("U3", "RBC", "A+", "2026-10-20", "2026-12-01", "HSP-2", "in_stock", "", "False", "2026-10-22"),
    ("U4", "RBC", "B+", "2026-10-30", "2026-12-11", "RBTC-A", "in_stock", "", "False", "2026-11-03"),
    ("U5", "RBC", "O+", "2026-10-10", "2026-11-21", "HSP-1", "in_stock", "", "False", "2026-10-12"),
    ("U6", "RBC", "O+", "2026-10-05", "2026-11-16", "HSP-2", "in_stock", "", "True", "2026-10-07"),
    ("U7", "RBC", "", "2026-10-18", "2026-11-29", "RBTC-A", "in_stock", "", "False", "2026-10-20"),
    ("U8", "RBC", "O+", "2026-10-01", "2026-11-12", "HSP-1", "transfused", "2026-10-31", "False", "2026-10-03"),
    ("U9", "RBC", "O+", "2026-09-22", "2026-11-03", "RBTC-A", "in_stock", "", "False", "2026-09-24"),
    ("U10", "PLT", "O+", "2026-10-29", "2026-11-03", "RBTC-A", "in_stock", "", "False", "2026-10-30"),
    ("U11", "RBC", "O+", "2026-10-16", "2026-11-27", "RBTC-A", "in_stock", "", "False", "2026-10-18"),
    ("U12", "RBC", "O+", "2026-10-17", "2026-11-28", "RBTC-A", "in_stock", "", "False", "2026-10-19"),
]

TRANSFERS = """transfer_id,unit_id,from_facility_id,to_facility_id,transfer_type,request_id,dispatched_at,received_at,transport_mode,coolbox_max_temp_c
T1,U1,RBTC-A,HSP-1,routine,,2026-10-19 08:00:00,2026-10-19 10:30:00,vehicle,4.6
T3,U3,RBTC-A,HSP-2,routine,,2026-10-31 22:00:00,2026-11-01 05:00:00,vehicle,4.8
T5,U5,RBTC-A,HSP-1,routine,,2026-10-15 09:00:00,,vehicle,4.9
T6,U6,RBTC-A,HSP-2,routine,,2026-10-10 09:00:00,2026-10-10 13:00:00,motorbike,12.0
T8,U8,RBTC-A,HSP-1,routine,,2026-10-30 09:00:00,2026-10-30 11:00:00,vehicle,4.7
"""

DAILY_STOCK = """date,facility_id,component,blood_group,units_in_stock_end_of_day
2026-10-31,HSP-1,RBC,O+,2
2026-10-31,RBTC-A,RBC,O+,4
2026-10-31,HSP-2,RBC,O+,1
2026-10-31,RBTC-A,PLT,O+,1
"""

OUTAGES = """outage_id,facility_id,start_time,end_time,duration_hours,backup_power_engaged
OUT-1,HSP-2,2026-10-12 10:00:00,2026-10-12 13:00:00,3.0,False
OUT-2,RBTC-A,2026-10-20 10:00:00,2026-10-20 15:00:00,5.0,True
OUT-3,HSP-1,2026-10-05 10:00:00,2026-10-05 12:00:00,2.0,False
"""

REQUESTS = """request_id,facility_id,facility_name_raw,requested_at,clinical_indication,patient_sex,patient_age_band,patient_blood_group,component_requested,units_requested,urgency,units_issued,units_issued_group_substituted,units_from_local_stock,emergency_supplied_from_id,last_unit_available_at,outcome
R1,HSP-1,Hospital One,2026-10-30 10:00:00,surgery,F,25-34,O+,RBC,2,routine,2,0,2,,2026-10-30 10:40:00,fulfilled
R2,HSP-1,HOSPITAL  ONE,2026-10-30 11:00:00,trauma_road_traffic,M,15-24,unknown,RBC,3,emergency,1,1,1,,2026-10-30 12:00:00,partially_fulfilled
R3,HSP-2,Hosp. Two,2026-10-31 09:00:00,other,M,35-49,A+,RBC,1,urgent,0,0,0,,,not_fulfilled
"""


def _temperature_logs() -> str:
    """Hourly fridge readings 1-31 October 2026, normal 4.0 C, with planted events."""
    rows = ["facility_id,recorded_at,temp_c"]
    start = datetime(2026, 10, 1)
    for site in ("RBTC-A", "HSP-1", "HSP-2"):
        for h in range(31 * 24):
            t = start + timedelta(hours=h)
            temp = 4.0
            if site == "HSP-1" and datetime(2026, 10, 25, 2) <= t < datetime(2026, 10, 25, 5):
                temp = 7.5                      # 3-hour excursion while U1 and U5 are on the shelf
            if site == "HSP-1" and t == datetime(2026, 10, 26, 0):
                temp = 6.8                      # single warm reading: below the event threshold
            if site == "RBTC-A" and t == datetime(2026, 10, 22, 3):
                temp = 99.9                     # sensor glitch, not an excursion
            if site == "RBTC-A" and t == datetime(2026, 10, 22, 4):
                temp = 0.0                      # sensor glitch
            if site == "HSP-2" and datetime(2026, 10, 28, 0) <= t < datetime(2026, 10, 28, 10):
                continue                        # 10-hour logger gap while U6 is on the shelf
            rows.append(f"{site},{t:%Y-%m-%d %H:%M:%S},{temp}")
    return "\n".join(rows) + "\n"


@pytest.fixture
def mini_raw(tmp_path):
    files = {
        "facilities": FACILITIES, "routes": ROUTES, "transfers": TRANSFERS, "daily_stock": DAILY_STOCK,
        "power_outages": OUTAGES, "requests": REQUESTS, "temperature_logs": _temperature_logs(),
        "donations": DONATIONS_HEADER + "".join(
            f"D-{u[0]},DN-{u[0]},,{u[3]},RBTC-A,collected,,450,non_reactive,,{u[9]}\n" for u in UNITS),
        "units": UNITS_HEADER + "".join(
            f"{u[0]},D-{u[0]},{u[1]},{u[2]},{u[3]},{u[4]},RBTC-A,{u[5]},{u[6]},{u[7]},{u[8]},,False\n"
            for u in UNITS),
    }
    for name, text in files.items():
        (tmp_path / f"{name}.csv").write_text(text)
    return tmp_path


@pytest.fixture
def mini_tables(mini_raw):
    tables, _ = load_all(mini_raw, ["facilities", "routes", "donations", "units", "transfers",
                                    "daily_stock", "power_outages", "requests", "temperature_logs"])
    return tables
