"""Expected extra units used when a batch moves, and batch construction.

Every score here comes from ranking.queue.fefo_use_probabilities, the one calculation path
shared with ranking.score, ranking.annotate and ranking.evaluate. All quantities are expected
units under the model's assumptions (synthetic data), never observed outcomes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from ranking.config import RankingConfig
from ranking.demand import DemandModel
from ranking.queue import fefo_use_probabilities
from ranking.timing import decide_dispatch


def expected_use(
    days_left: Sequence[int], rates: np.ndarray, size_pmf: Sequence[float], cap_extra: int = 6
) -> float:
    """EU(queue): expected number of units of the queue used before they expire."""
    left = np.sort(np.asarray(days_left, dtype=int))
    if left.size == 0:
        return 0.0
    return float(fefo_use_probabilities(left, rates, size_pmf, cap_extra).sum())


def _without(queue: Sequence[int], removed: Sequence[int]) -> list[int]:
    """The multiset `queue` minus one occurrence of each value of `removed`."""
    remaining = sorted(queue)
    for value in removed:
        try:
            remaining.remove(value)
        except ValueError as exc:
            raise ValueError(
                f"moved unit with {value} days left is not in the sender queue"
            ) from exc
    return remaining


def marginal_gain(
    sender_days_left: list[int],
    destination_days_left: list[int],
    moved_days_left: list[int],
    sender_rates: list[float],
    destination_rates: list[float],
    size_pmf: tuple[float, ...],
) -> float:
    """EU_dest(with batch) - EU_dest + EU_sender(without batch) - EU_sender, with EU the sum of
    the unit use probabilities of a queue. Exact when the batch arrives on day 0.

    `sender_days_left` is the whole sender queue, the moved units included; `moved_days_left`
    are the days left of the moved units (one occurrence each is taken out of the sender).
    """
    s_rates, d_rates = np.asarray(sender_rates, float), np.asarray(destination_rates, float)
    remaining = _without(sender_days_left, moved_days_left)
    destination_after = list(destination_days_left) + list(moved_days_left)
    return (
        expected_use(destination_after, d_rates, size_pmf)
        - expected_use(destination_days_left, d_rates, size_pmf)
        + expected_use(remaining, s_rates, size_pmf)
        - expected_use(sender_days_left, s_rates, size_pmf)
    )


def arrival_lag_days(travel_hours: float, arrival_allowance_hours: float) -> int:
    """a = ceil((travel hours + arrival allowance) / 24): days before a shipped unit is usable."""
    return math.ceil((travel_hours + arrival_allowance_hours) / 24)


def max_wait_days(
    moved_days_left: Sequence[int], arrival_lag: int, min_remaining_days: int, config: RankingConfig
) -> int:
    """T = min(max_wait_days, shortest life in the batch - arrival lag - required life), >= 0."""
    slack = min(moved_days_left) - arrival_lag - min_remaining_days
    return max(0, min(config.max_wait_days, slack))


def aged_positions(
    left: np.ndarray, rates: np.ndarray, days: int, size_pmf: Sequence[float], cap_extra: int
) -> np.ndarray:
    """Positions of the units of a sorted queue still on the shelf after `days` days.

    The expected number of units used in the meantime (same recursion, every expiry cut at
    `days`) is rounded and taken from the oldest end; units that have expired are dropped.
    """
    if days == 0 or left.size == 0:
        return np.arange(left.size)
    used = fefo_use_probabilities(np.minimum(left, days), rates, size_pmf, cap_extra).sum()
    kept = np.arange(left.size)[int(round(used)) :]
    return kept[left[kept] > days]


def gain_by_day(
    sender_days_left: Sequence[int],
    destination_days_left: Sequence[int],
    moved_days_left: Sequence[int],
    sender_rates: Sequence[float],
    destination_rates: Sequence[float],
    size_pmf: Sequence[float],
    *,
    arrival_lag: int,
    max_tau: int,
    cap_extra: int = 6,
) -> tuple[float, ...]:
    """G(tau) for a dispatch on day tau = 0..max_tau, the batch usable `arrival_lag` days later.

    For each moved unit u: V(u) = pi_loc(u, tau) + (1 - pi_loc(u, tau)) * p_dest(u, tau), with
    pi_loc the chance it is used at the sender before tau (every sender expiry cut at tau) and
    p_dest its marginal value at the destination queue aged to the arrival day (batch units
    added in expiry order). G(tau) = sum V(u) - sum p_stay(u) + w * R(tau), where R is what the
    sender's other units gain once the batch has left (sender queue aged to tau) and w the mean
    chance that a batch unit is still there to leave. G(0) with arrival_lag = 0 equals
    marginal_gain exactly; otherwise this is the approximation checked against
    ranking.simulate.simulate_transfer_gain. Rates must cover every days_left of both queues.
    """
    s_left = np.sort(np.asarray(sender_days_left, dtype=int))
    d_left = np.sort(np.asarray(destination_days_left, dtype=int))
    s_rates, d_rates = np.asarray(sender_rates, float), np.asarray(destination_rates, float)
    moved = sorted(int(v) for v in moved_days_left)
    if not moved:
        return (0.0,) * (max_tau + 1)
    # The batch takes the last position among tied units (the order within a tie is arbitrary).
    batch: list[int] = []
    for value in moved:
        candidates = [i for i in np.flatnonzero(s_left == value) if i not in batch]
        if not candidates:
            raise ValueError(f"moved unit with {value} days left is not in the sender queue")
        batch.append(int(candidates[-1]))
    batch_idx = np.array(batch)
    p_stay = fefo_use_probabilities(s_left, s_rates, size_pmf, cap_extra)

    gains = []
    for tau in range(max_tau + 1):
        arrival = tau + arrival_lag
        if tau == 0:
            pi_loc = np.zeros(len(batch))
        else:
            cut = np.minimum(s_left, tau)
            pi_loc = fefo_use_probabilities(cut, s_rates, size_pmf, cap_extra)[batch_idx]

        d_kept = d_left[aged_positions(d_left, d_rates, arrival, size_pmf, cap_extra)] - arrival
        d_future = d_rates[arrival:]
        queue = list(d_kept)
        previous = expected_use(queue, d_future, size_pmf, cap_extra)
        value = 0.0
        for k, idx in enumerate(batch_idx):
            life = int(s_left[idx]) - arrival
            contribution = 0.0
            if life >= 1:
                queue.append(life)
                current = expected_use(queue, d_future, size_pmf, cap_extra)
                contribution, previous = current - previous, current
            value += pi_loc[k] + (1.0 - pi_loc[k]) * contribution

        s_kept = aged_positions(s_left, s_rates, tau, size_pmf, cap_extra)
        s_future = s_rates[tau:]
        is_batch = np.isin(s_kept, batch_idx)
        with_batch = fefo_use_probabilities(s_left[s_kept] - tau, s_future, size_pmf, cap_extra)
        others_alone = expected_use(s_left[s_kept[~is_batch]] - tau, s_future, size_pmf, cap_extra)
        rank_gain = others_alone - float(with_batch[~is_batch].sum())
        still_there = float(np.mean(1.0 - pi_loc))
        gains.append(value - float(p_stay[batch_idx].sum()) + still_there * rank_gain)
    return tuple(gains)


def _queues(stock: pd.DataFrame, origin, config: RankingConfig) -> dict[tuple[str, str], list]:
    """(facility_id, blood_group) -> sorted list of (days_left, unit_id) of the pooled units."""
    pooled = stock[stock["component"].isin(config.pool_components) & stock["blood_group"].notna()]
    left = (pd.to_datetime(pooled["expiry_date"]).dt.normalize() - pd.Timestamp(origin)).dt.days + 1
    queues: dict[tuple[str, str], list] = {}
    for site, group, days, unit in zip(
        pooled["facility_id"], pooled["blood_group"], left, pooled["unit_id"], strict=True
    ):
        if days >= 1:
            queues.setdefault((site, group), []).append((int(days), unit))
    return {key: sorted(value) for key, value in queues.items()}


def plan_batches(
    eligible_moves: pd.DataFrame,
    stock: pd.DataFrame,
    demand: DemandModel,
    config: RankingConfig,
    *,
    arrival_allowance_hours: float = 6.0,
    sender_reserve_units: int = 2,
    min_remaining_days: int = 7,
    routine_runs: Mapping[tuple[str, str], frozenset[int]] | None = None,
) -> pd.DataFrame:
    """Greedy with re-scoring: accept the best (unit, destination), update both queues, recompute
    the remaining gains of that site and group, stop at min_gain_units, the sender reserve or the
    cooler capacity; group by (origin, destination, day).

    `eligible_moves` holds only moves the pipeline eligibility allowed (unit_id,
    from_facility_id, to_facility_id, blood_group, component, typical_travel_hours): nothing else
    is ever proposed. `stock` is every unit on every shelf (the queues). The reserve counts the
    eligible units of the same component and group left at the sender. Each batch then gets its
    dispatch day from ranking.timing.decide_dispatch; `routine_runs` maps (from, to) to the
    weekdays of a routine vehicle on that route (none: every trip is a special trip).
    """
    columns = [
        "batch_id", "unit_id", "from_facility_id", "to_facility_id", "blood_group", "component",
        "unit_gain", "batch_gain_now", "send_by", "net_gain", "waiting_cost_per_day",
        "uses_routine_run", "suggested", "reason",
    ]  # fmt: skip
    if eligible_moves.empty:
        return pd.DataFrame(columns=columns)
    origin = demand.origin
    routine_runs = routine_runs or {}
    queues = _queues(stock, origin, config)
    horizon = max([d for q in queues.values() for d, _ in q] + [1])
    rates: dict[tuple[str, str], np.ndarray] = {}

    def rate(key: tuple[str, str]) -> np.ndarray:
        """Daily request rates of a (site, group) over the whole horizon, cached."""
        if key not in rates:
            rates[key] = demand.request_rates(key[0], key[1], horizon)
        return rates[key]

    moves = eligible_moves.drop_duplicates(["unit_id", "to_facility_id"]).to_dict("records")
    days_of = {u: d for q in queues.values() for d, u in q}
    lag_of = {
        (m["from_facility_id"], m["to_facility_id"]): arrival_lag_days(
            float(m["typical_travel_hours"]), arrival_allowance_hours
        )
        for m in moves
    }
    available = (
        eligible_moves.drop_duplicates("unit_id")
        .groupby(["from_facility_id", "component", "blood_group"])
        .size()
        .to_dict()
    )
    cache: dict[int, float] = {}
    moved: dict[str, tuple] = {}
    batch_size: dict[tuple[str, str], int] = {}

    def single_gain(i: int) -> float:
        """Gain of moving the unit of move i alone, today, with the current queues."""
        if i not in cache:
            m = moves[i]
            s_key = (m["from_facility_id"], m["blood_group"])
            d_key = (m["to_facility_id"], m["blood_group"])
            cache[i] = gain_by_day(
                [d for d, _ in queues.get(s_key, [])],
                [d for d, _ in queues.get(d_key, [])],
                [days_of[m["unit_id"]]],
                rate(s_key),
                rate(d_key),
                demand.size_pmf,
                arrival_lag=lag_of[(m["from_facility_id"], m["to_facility_id"])],
                max_tau=0,
                cap_extra=config.cap_extra,
            )[0]
        return cache[i]

    while True:
        best, best_gain = None, -math.inf
        for i, m in enumerate(moves):
            unit, route = m["unit_id"], (m["from_facility_id"], m["to_facility_id"])
            left_key = (m["from_facility_id"], m["component"], m["blood_group"])
            if unit in moved or unit not in days_of:
                continue
            if available.get(left_key, 0) - 1 < sender_reserve_units:
                continue
            if batch_size.get(route, 0) >= config.cooler_capacity_units:
                continue
            gain = single_gain(i)
            if gain > best_gain:
                best, best_gain = i, gain
        if best is None or best_gain < config.min_gain_units:
            break
        m = moves[best]
        s_key, d_key = (
            (m["from_facility_id"], m["blood_group"]),
            (m["to_facility_id"], m["blood_group"]),
        )
        entry = (days_of[m["unit_id"]], m["unit_id"])
        queues[s_key].remove(entry)
        queues[d_key] = sorted(queues.get(d_key, []) + [entry])
        route = (m["from_facility_id"], m["to_facility_id"])
        moved[m["unit_id"]] = (m, best_gain)
        batch_size[route] = batch_size.get(route, 0) + 1
        left_key = (m["from_facility_id"], m["component"], m["blood_group"])
        available[left_key] = available.get(left_key, 0) - 1
        touched = {s_key, d_key}
        for i in list(cache):
            other = moves[i]
            keys = {(other["from_facility_id"], other["blood_group"]),
                    (other["to_facility_id"], other["blood_group"])}  # fmt: skip
            if keys & touched:
                del cache[i]

    rows = []
    by_route: dict[tuple[str, str, str], list] = {}
    for m, gain in moved.values():
        by_route.setdefault(
            (m["from_facility_id"], m["to_facility_id"], m["blood_group"]), []
        ).append((m, gain))
    for number, ((src, dst, group), members) in enumerate(sorted(by_route.items()), start=1):
        batch_days = [days_of[m["unit_id"]] for m, _ in members]
        s_key, d_key = (src, group), (dst, group)
        sender_before = [d for d, _ in queues.get(s_key, [])] + batch_days
        destination_before = _without([d for d, _ in queues.get(d_key, [])], batch_days)
        lag = lag_of[(src, dst)]
        gains = gain_by_day(
            sender_before, destination_before, batch_days, rate(s_key), rate(d_key),
            demand.size_pmf, arrival_lag=lag,
            max_tau=max_wait_days(batch_days, lag, min_remaining_days, config),
            cap_extra=config.cap_extra,
        )  # fmt: skip
        decision = decide_dispatch(
            gains, routine_runs.get((src, dst), frozenset()), config, origin=origin
        )
        for m, gain in members:
            rows.append(
                {
                    "batch_id": f"B{number:03d}", "unit_id": m["unit_id"],
                    "from_facility_id": src, "to_facility_id": dst, "blood_group": group,
                    "component": m["component"], "unit_gain": gain, "batch_gain_now": gains[0],
                    "send_by": decision.send_by, "net_gain": decision.net_gain,
                    "waiting_cost_per_day": decision.waiting_cost_per_day,
                    "uses_routine_run": decision.uses_routine_run,
                    "suggested": decision.send_by is not None, "reason": decision.reason,
                }
            )  # fmt: skip
    return pd.DataFrame(rows, columns=columns)
