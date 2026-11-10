"""DG-08: per-component shelf life and eligibility; platelets stay behind a flag."""

from __future__ import annotations

import pandas as pd

from pipeline.config import PipelineConfig, load_config
from pipeline.eligibility import check_move, component_catalog, shelf_life_check, unit_eligibility
from pipeline.snapshot import build_snapshot

CFG = PipelineConfig()
AS_OF = pd.Timestamp("2026-10-31 23:59:59")


def test_config_carries_a_policy_per_component():
    cfg = load_config()
    assert {c: p.shelf_life_days for c, p in cfg.components.items()} == {
        "RBC": 42, "WB": 35, "PLT": 5, "FFP": 365, "CRYO": 365}
    assert cfg.enabled_components() == ("RBC",)
    assert cfg.policy("PLT").max_travel_hours == 6.0


def test_configured_shelf_lives_match_the_data(mini_tables):
    check = shelf_life_check(mini_tables["units"], CFG).set_index("component")
    assert check["matches"].all()
    assert check.loc["PLT", "observed_mode_days"] == 5


def test_shelf_life_mismatch_is_detected(mini_tables):
    wrong = load_config(None).components | {}
    wrong["RBC"] = type(wrong["RBC"])(35, True)
    cfg = PipelineConfig(components=wrong)
    check = shelf_life_check(mini_tables["units"], cfg).set_index("component")
    assert not check.loc["RBC", "matches"]


def test_rbc_default_scope_is_unchanged_by_platelet_settings(mini_tables):
    snap = build_snapshot(mini_tables, CFG)
    default = unit_eligibility(snap.units, CFG, snap.as_of)
    with_plt = unit_eligibility(snap.units, CFG.with_components_enabled("PLT"), snap.as_of)
    rbc = lambda r: set(r.eligible.loc[r.eligible["component"] == "RBC", "unit_id"])  # noqa: E731
    assert rbc(default) == rbc(with_plt)
    assert "U10" not in set(default.eligible["unit_id"])
    assert "U10" in set(with_plt.eligible["unit_id"])


def test_platelets_carry_a_missing_evidence_warning(mini_tables):
    snap = build_snapshot(mini_tables, CFG)
    res = unit_eligibility(snap.units, CFG.with_components_enabled("PLT"), snap.as_of).units
    res = res.set_index("unit_id")
    assert res.loc["U10", "warnings"] == ("no_storage_evidence",)
    assert res.loc["U2", "warnings"] == ()


def test_component_catalog_for_the_api():
    cat = {c["component"]: c for c in component_catalog(CFG)}
    assert cat["RBC"]["enabled_in_queue"] and cat["RBC"]["storage_range_c"] == [2.0, 6.0]
    assert not cat["PLT"]["enabled_in_queue"] and not cat["PLT"]["storage_evidence_in_dataset"]
    assert cat["PLT"]["max_travel_hours"] == 6.0


def test_platelets_have_a_tighter_routing_policy(mini_tables):
    cfg = CFG.with_components_enabled("PLT")
    snap = build_snapshot(mini_tables, cfg)
    unit = snap.units.set_index("unit_id").loc["U10"].to_dict() | {"unit_id": "U10"}
    common = dict(as_of=AS_OF, config=cfg, routes=mini_tables["routes"],
                  facilities=mini_tables["facilities"], sender_available=4, recipient_gap=1)
    near = check_move(unit, "HSP-1", **common)            # 2 h road
    assert near["ok"], near["reasons"]
    short = PipelineConfig(components=cfg.components | {
        "PLT": type(cfg.policy("PLT"))(5, True, 24.0, max_travel_hours=2.5)})
    far = check_move(unit, "HSP-2", **(common | {"config": short}))  # 3 h road
    assert "route_too_long_for_component" in far["reasons"]
