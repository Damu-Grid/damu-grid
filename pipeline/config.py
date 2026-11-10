"""Shared pipeline settings (ADR-006): shelf lives, eligibility limits, cold-chain thresholds.

Every limit here is a documented team default chosen in-window, not a regulation. A second
country is a settings change: load another TOML file with `load_config(path)`. The backend
settings API should read and write this same object.
"""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from pipeline.schema import BLOOD_GROUPS, HOSPITAL_TYPES

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "settings" / "kenya_default.toml"


@dataclass(frozen=True)
class ComponentPolicy:
    shelf_life_days: int
    # Suggestable in the live review queue. Tier 1 = RBC only (AGENTS.md).
    enabled_in_queue: bool = False
    # Remaining life required after the unit is expected to arrive (team default, configurable).
    min_remaining_hours_on_arrival: float = 168.0
    # Safe storage range from the data dictionary; None = not given, fridge logs not applicable.
    storage_min_c: float | None = None
    storage_max_c: float | None = None


@dataclass(frozen=True)
class PipelineConfig:
    country: str = "KE"
    # End of the modelled year, EAT (docs/DATA.md snapshot convention).
    as_of: str = "2026-10-31T23:59:59+03:00"
    components: dict[str, ComponentPolicy] = field(default_factory=lambda: {
        "RBC": ComponentPolicy(42, True, 168.0, 2.0, 6.0),
        "WB": ComponentPolicy(35, False, 168.0, 2.0, 6.0),
        "PLT": ComponentPolicy(5, False, 24.0, None, None),
        "FFP": ComponentPolicy(365, False, 720.0, None, None),
        "CRYO": ComponentPolicy(365, False, 720.0, None, None),
    })
    known_blood_groups: tuple[str, ...] = BLOOD_GROUPS
    # Extra hours on top of routes.typical_travel_hours before a unit counts as arrived.
    arrival_allowance_hours: float = 6.0
    # Units of the same component and group a sender must keep after a move (team default).
    default_sender_reserve_units: int = 2
    recipient_facility_types: tuple[str, ...] = HOSPITAL_TYPES
    # Cold chain (data dictionary): cool box above 10 C is an excursion.
    coolbox_max_c: float = 10.0
    # Sensor glitch values (data dictionary); never treated as clinical events.
    glitch_values: tuple[float, ...] = (-99.0, 99.9, 0.0)
    # Consecutive hourly readings out of range that make an excursion event (team default).
    excursion_min_hours: int = 2
    # Logger silence longer than this is missing evidence (team default).
    logger_gap_hours: int = 6
    # Outage without backup at least this long is evidence of a possible excursion.
    outage_min_hours: float = 1.0
    # Which evidence types stop a unit being suggested. Missing evidence is conservative.
    blocking_flags: tuple[str, ...] = (
        "fridge_excursion", "outage_no_backup", "coolbox_excursion", "logger_gap", "receipt_unconfirmed",
    )

    def policy(self, component: str) -> ComponentPolicy:
        return self.components[component]

    def enabled_components(self) -> tuple[str, ...]:
        return tuple(c for c, p in self.components.items() if p.enabled_in_queue)

    def with_components_enabled(self, *components: str) -> PipelineConfig:
        comps = {c: replace(p, enabled_in_queue=p.enabled_in_queue or c in components)
                 for c, p in self.components.items()}
        return replace(self, components=comps)

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path | None = DEFAULT_CONFIG_PATH) -> PipelineConfig:
    """Defaults overridden by a TOML file (missing keys keep their defaults)."""
    base = PipelineConfig()
    if path is None or not Path(path).exists():
        return base
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    comps = dict(base.components)
    for name, values in data.pop("components", {}).items():
        comps[name] = replace(comps[name], **values) if name in comps else ComponentPolicy(**values)
    tuples = {k: tuple(v) for k, v in data.items() if isinstance(v, list)}
    return replace(base, components=comps, **{**data, **tuples})
