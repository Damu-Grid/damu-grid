"""Best dispatch day: waiting cost against the cost of a trip."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ranking.config import RankingConfig


@dataclass(frozen=True)
class DispatchDecision:
    send_by: date | None  # None = no suggestion (net gain below min_gain_units)
    net_gain: float
    gain_by_day: tuple[float, ...]  # G(tau) for tau = 0..T
    waiting_cost_per_day: float  # G(0) - G(1)
    uses_routine_run: bool
    reason: str  # built only from the numbers above


def decide_dispatch(
    gain_by_day: tuple[float, ...],
    routine_run_days: frozenset[int],
    config: RankingConfig,
) -> DispatchDecision:
    """net(tau) = G(tau) - trip_cost(tau), trip_cost = 0 on a routine-run day, trip_cost_units
    otherwise; tau* = argmax net. G(tau) for tau > 0 uses the conditional waiting value
    pi_loc + (1 - pi_loc) * p_dest (see the plan, 3.3). Step 5."""
    raise NotImplementedError("DG-19 step 5")
