import hashlib
import logging
import math
import sqlite3
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from backend.app.schemas import Suggestion, Uncertainty
from backend.app.services import SuggestionServiceUnavailable
from pipeline.config import PipelineConfig, load_config
from pipeline.eligibility import NetworkIndex, check_move, unit_eligibility
from ranking.annotate import (
    AnnotationInputs,
    BatchAnnotation,
    annotate_batch,
    load_annotation_inputs,
)
from ranking.config import RankingConfig

LOGGER = logging.getLogger(__name__)
# Survival-score inputs and batch annotations, shared across requests for one database file and
# as-of time (the snapshot does not change between requests; eligibility is rechecked each time).
_RANKING_STATE: dict[str, Any] = {}
_RANKING_LOCK = Lock()
RANKING_CONFIG = RankingConfig()
BATCH_COLUMNS = ["unit_id", "facility_id", "blood_group", "component", "expiry_date"]
ANNOTATED_NUMBERS = (
    "expected_use_if_stays",
    "expected_use_if_moved",
    "survival_score_if_stays",
    "survival_score_if_moved",
)


class SQLiteSuggestionProvider:
    def __init__(self, database_path: Path, as_of: datetime | None) -> None:
        self.database_path = database_path
        self.as_of = as_of

    def suggest(
        self,
        policy: str,
        settings: dict[str, Any],
        excluded_unit_ids: set[str],
        pending_inbound: dict[tuple[str, str], int] | None = None,
    ) -> list[Suggestion]:
        context = self._load_context(settings, excluded_unit_ids, pending_inbound)
        proposals: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        for unit in context["units"]:
            source_key = (unit["facility_id"], unit["component"], unit["blood_group"])
            for destination_key, gap in context["gaps"].items():
                destination, component, group = destination_key
                if (
                    component != unit["component"]
                    or group != unit["blood_group"]
                    or destination == unit["facility_id"]
                    or gap <= 0
                ):
                    continue
                move = self._check_move(
                    context,
                    unit,
                    destination,
                    sender_available=context["stock"][source_key],
                    recipient_gap=gap,
                    units_moving=1,
                    settings=settings,
                )
                if not move["ok"]:
                    continue
                if policy == "expiry_aware":
                    key = (
                        unit["expiry_date"],
                        -gap,
                        move["typical_travel_hours"],
                        unit["unit_id"],
                        destination,
                    )
                else:
                    key = (
                        move["typical_travel_hours"],
                        unit["expiry_date"],
                        -gap,
                        unit["unit_id"],
                        destination,
                    )
                proposals.append(
                    (key, {"destination": destination, "gap": gap, "unit": unit})
                )

        proposals.sort(key=lambda item: item[0])
        outbound: Counter[tuple[str, str, str]] = Counter()
        inbound: Counter[tuple[str, str, str]] = Counter()
        used_units: set[str] = set()
        suggestions: list[Suggestion] = []

        for _, proposal in proposals:
            unit = proposal["unit"]
            destination = proposal["destination"]
            source_key = (unit["facility_id"], unit["component"], unit["blood_group"])
            destination_key = (destination, unit["component"], unit["blood_group"])
            if unit["unit_id"] in used_units:
                continue
            gap = context["gaps"][destination_key] - inbound[destination_key]
            move = self._check_move(
                context,
                unit,
                destination,
                sender_available=context["stock"][source_key],
                recipient_gap=gap,
                units_moving=outbound[source_key] + 1,
                settings=settings,
            )
            if not move["ok"]:
                continue

            outbound[source_key] += 1
            inbound[destination_key] += 1
            used_units.add(unit["unit_id"])
            route = context["network"].routes[
                (unit["facility_id"], destination)
            ]
            suggestions.append(
                self._build_suggestion(
                    context,
                    [unit],
                    destination,
                    route,
                    context["stock"][source_key] - outbound[source_key],
                    gap,
                    policy,
                    settings,
                )
            )
        return suggestions

    def is_eligible(
        self,
        suggestion: Suggestion,
        settings: dict[str, Any],
        excluded_unit_ids: set[str],
        pending_inbound: dict[tuple[str, str], int] | None = None,
    ) -> bool:
        context = self._load_context(
            settings,
            excluded_unit_ids - set(suggestion.unit_ids),
            pending_inbound,
        )
        units_by_id = {unit["unit_id"]: unit for unit in context["units"]}
        selected = [units_by_id.get(unit_id) for unit_id in suggestion.unit_ids]
        if any(unit is None for unit in selected):
            return False
        concrete = [unit for unit in selected if unit is not None]
        if any(
            unit["facility_id"] != suggestion.from_facility_id
            or unit["component"] != suggestion.component
            or unit["blood_group"] != suggestion.blood_group
            for unit in concrete
        ):
            return False
        return self._validate_selection(context, concrete, suggestion.to_facility_id, settings)

    def change(
        self,
        original: Suggestion,
        unit_ids: list[str],
        destination: str,
        settings: dict[str, Any],
        excluded_unit_ids: set[str],
        pending_inbound: dict[tuple[str, str], int] | None = None,
    ) -> Suggestion:
        context = self._load_context(
            settings,
            excluded_unit_ids - set(original.unit_ids),
            pending_inbound,
        )
        if not unit_ids or len(set(unit_ids)) != len(unit_ids):
            raise ValueError("Changed unit IDs must be nonempty and unique.")
        units_by_id = {unit["unit_id"]: unit for unit in context["units"]}
        selected = [units_by_id.get(unit_id) for unit_id in unit_ids]
        if any(unit is None for unit in selected):
            raise ValueError("One or more selected units are unavailable.")
        concrete = [unit for unit in selected if unit is not None]
        if not self._validate_selection(context, concrete, destination, settings):
            raise ValueError("The changed move does not pass current eligibility rules.")

        first = concrete[0]
        source_key = (first["facility_id"], first["component"], first["blood_group"])
        destination_key = (destination, first["component"], first["blood_group"])
        route = context["network"].routes[(first["facility_id"], destination)]
        changed_id = _suggestion_id(context["as_of"], unit_ids[0])
        return self._build_suggestion(
            context,
            concrete,
            destination,
            route,
            context["stock"][source_key] - len(concrete),
            context["gaps"][destination_key],
            original.policy,
            settings,
            suggestion_id=changed_id,
        )

    def _load_context(
        self,
        settings: dict[str, Any],
        excluded_unit_ids: set[str],
        pending_inbound: dict[tuple[str, str], int] | None = None,
    ) -> dict[str, Any]:
        if self.as_of is None or self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise SuggestionServiceUnavailable("AS_OF_DATE must be a timezone-aware date.")
        if not self.database_path.is_file():
            raise SuggestionServiceUnavailable("The processed pipeline snapshot is not available.")

        reserve = settings.get("sender_reserve_units")
        remaining_life = settings.get("remaining_life_min_days", {}).get("RBC")
        if (
            not isinstance(reserve, int)
            or isinstance(reserve, bool)
            or reserve < 0
            or not isinstance(remaining_life, int)
            or isinstance(remaining_life, bool)
            or remaining_life < 0
        ):
            raise SuggestionServiceUnavailable(
                "RBC reserve or remaining-life settings are invalid."
            )

        expected_as_of = self.as_of.isoformat(timespec="seconds")
        required_tables = {
            "facilities",
            "routes",
            "requests",
            "dg_snapshot_meta",
            "dg_snapshot_units",
            "dg_cold_chain_flags",
        }
        uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                available_tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                missing = sorted(required_tables - available_tables)
                if missing:
                    raise SuggestionServiceUnavailable(
                        "The verified pipeline snapshot is incomplete; run "
                        "`uv run python -m pipeline build`."
                    )
                metadata = connection.execute(
                    "SELECT as_of FROM dg_snapshot_meta"
                ).fetchall()
                if expected_as_of not in {row[0] for row in metadata}:
                    raise SuggestionServiceUnavailable(
                        "The pipeline snapshot date does not match AS_OF_DATE; "
                        "rebuild the snapshot."
                    )

                snapshot = pd.read_sql_query(
                    "SELECT unit_id, facility_id, component, blood_group, expiry_date, status, "
                    "temp_excursion_exposed, receipt_status FROM dg_snapshot_units WHERE as_of = ?",
                    connection,
                    params=(expected_as_of,),
                )
                unit_flags = pd.read_sql_query(
                    "SELECT unit_id, flag_type, blocks_suggestion FROM dg_cold_chain_flags "
                    "WHERE scope = 'unit'",
                    connection,
                )
                facilities = pd.read_sql_query(
                    "SELECT facility_id, name, facility_type FROM facilities", connection
                )
                routes = pd.read_sql_query(
                    "SELECT from_facility_id, to_facility_id, typical_travel_hours, road_quality "
                    "FROM routes",
                    connection,
                )
                window_start = self.as_of.date() - timedelta(days=27)
                window_end = self.as_of.date() + timedelta(days=1)
                requests = pd.read_sql_query(
                    "SELECT facility_id, requested_at, patient_blood_group, units_requested "
                    "FROM requests WHERE component_requested = 'RBC' "
                    "AND requested_at >= ? AND requested_at < ?",
                    connection,
                    params=(window_start.isoformat(), window_end.isoformat()),
                )
        except (sqlite3.Error, pd.errors.DatabaseError) as exc:
            raise SuggestionServiceUnavailable(
                f"The processed pipeline snapshot cannot be read: {exc}"
            ) from exc

        base_config = load_config()
        components = dict(base_config.components)
        components["RBC"] = replace(
            components["RBC"],
            min_remaining_hours_on_arrival=float(remaining_life * 24),
        )
        config: PipelineConfig = replace(
            base_config,
            components=components,
            default_sender_reserve_units=reserve,
        )
        snapshot["expiry_date"] = pd.to_datetime(snapshot["expiry_date"], errors="coerce")
        snapshot = snapshot[snapshot["expiry_date"].notna()].copy()
        as_of_naive = pd.Timestamp(self.as_of.replace(tzinfo=None))
        eligibility = unit_eligibility(
            snapshot,
            config,
            as_of_naive,
            reserved_unit_ids=excluded_unit_ids,
            unit_flags=unit_flags,
        )

        facility_types = dict(
            zip(facilities["facility_id"], facilities["facility_type"], strict=True)
        )
        valid_routes = routes[
            routes["typical_travel_hours"].notna()
            & (routes["typical_travel_hours"] >= 0)
            & routes["road_quality"].notna()
            & routes["road_quality"].astype(str).str.strip().ne("")
        ].copy()
        network = NetworkIndex.build(valid_routes, facilities)

        requests["requested_at"] = pd.to_datetime(requests["requested_at"], errors="coerce")
        requests["units_requested"] = pd.to_numeric(
            requests["units_requested"], errors="coerce"
        )
        requested: Counter[tuple[str, str, str]] = Counter()
        for row in requests.itertuples(index=False):
            group = row.patient_blood_group
            facility = row.facility_id
            if (
                group not in config.known_blood_groups
                or facility_types.get(facility) not in config.recipient_facility_types
                or pd.isna(row.requested_at)
                or pd.isna(row.units_requested)
                or row.units_requested <= 0
            ):
                continue
            requested[(facility, "RBC", group)] += int(row.units_requested)

        stock: Counter[tuple[str, str, str]] = Counter()
        units = eligibility.eligible.sort_values(["expiry_date", "unit_id"]).to_dict("records")
        for unit in units:
            key = (unit["facility_id"], unit["component"], unit["blood_group"])
            stock[key] += 1

        gaps = {
            key: max(
                0,
                math.ceil(7 * units_requested / 28)
                - stock[key]
                - (pending_inbound or {}).get((key[0], key[2]), 0),
            )
            for key, units_requested in requested.items()
        }
        return {
            "as_of": self.as_of,
            "config": config,
            "facilities": facilities,
            "network": network,
            "routes": valid_routes,
            "gaps": gaps,
            "units": units,
            "stock": stock,
        }

    @staticmethod
    def _check_move(
        context: dict[str, Any],
        unit: dict[str, Any],
        destination: str,
        *,
        sender_available: int,
        recipient_gap: int,
        units_moving: int,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        return check_move(
            unit,
            destination,
            as_of=pd.Timestamp(context["as_of"].replace(tzinfo=None)),
            config=context["config"],
            routes=context["routes"],
            facilities=context["facilities"],
            sender_available=sender_available,
            recipient_gap=recipient_gap,
            sender_reserve=settings["sender_reserve_units"],
            units_moving=units_moving,
            index=context["network"],
        )

    def _validate_selection(
        self,
        context: dict[str, Any],
        units: list[dict[str, Any]],
        destination: str,
        settings: dict[str, Any],
    ) -> bool:
        if not units or destination not in context["network"].facility_types:
            return False
        first = units[0]
        source_key = (first["facility_id"], first["component"], first["blood_group"])
        destination_key = (destination, first["component"], first["blood_group"])
        if any(
            unit["facility_id"] != first["facility_id"]
            or unit["component"] != first["component"]
            or unit["blood_group"] != first["blood_group"]
            for unit in units
        ):
            return False
        gap = context["gaps"].get(destination_key, 0)
        if gap < len(units):
            return False
        for index, unit in enumerate(units):
            move = self._check_move(
                context,
                unit,
                destination,
                sender_available=context["stock"][source_key],
                recipient_gap=gap - index,
                units_moving=index + 1,
                settings=settings,
            )
            if not move["ok"]:
                return False
        return True

    def _build_suggestion(
        self,
        context: dict[str, Any],
        units: list[dict[str, Any]],
        destination: str,
        route: tuple[float | None, str | None],
        sender_stock_after: int,
        recipient_gap: int,
        policy: str,
        settings: dict[str, Any],
        suggestion_id: str | None = None,
    ) -> Suggestion:
        first = units[0]
        source = first["facility_id"]
        group = first["blood_group"]
        snapshot_time = context["as_of"]
        data_age = max(
            0.0, (datetime.now(snapshot_time.tzinfo) - snapshot_time).total_seconds() / 3600
        )
        facility_names = dict(
            zip(context["facilities"]["facility_id"], context["facilities"]["name"], strict=True)
        )
        suggestion = Suggestion(
            suggestion_id=suggestion_id or _suggestion_id(snapshot_time, first["unit_id"]),
            as_of=snapshot_time,
            data_age_hours=data_age,
            component=first["component"],
            blood_group=group,
            unit_ids=[unit["unit_id"] for unit in units],
            from_facility_id=source,
            to_facility_id=destination,
            from_facility_name=facility_names.get(source),
            to_facility_name=facility_names.get(destination),
            expiry_date=min(unit["expiry_date"] for unit in units).date(),
            send_by=None,
            typical_travel_hours=route[0],
            sender_reserve_units=settings["sender_reserve_units"],
            sender_stock_after=sender_stock_after,
            recipient_gap_units=recipient_gap,
            uncertainty=Uncertainty(
                method="trailing_28_day_request_average",
                nominal_level=None,
                label="Synthetic demand estimate, not a clinical probability.",
            ),
            reason_deterministic=(
                f"{len(units)} eligible RBC unit(s) are available above the sender reserve at "
                f"{source}. {destination} has an estimated {recipient_gap}-unit seven-day gap "
                "from the preceding 28 days of known-group requests. This is a synthetic estimate "
                "for coordinator review, not a transfusion decision."
            ),
            policy=policy,
            fallback=policy == "fallback",
            eligibility_ok=True,
            warnings=[
                "Synthetic request history is treated as complete; "
                "unrecorded demand is not measured."
            ],
        )
        return self._annotate(context, suggestion, units, destination, route, settings)

    def _ranking_inputs(self, context: dict[str, Any]) -> AnnotationInputs | None:
        """Complete shelves and demand model for the survival score.

        Loaded once per database file and as-of time, and shared by every request until the
        pipeline rebuilds the file. None when they cannot be loaded (an older or partial
        database): the suggestions then keep their survival fields empty instead of guessing.
        """
        try:
            stamp = self.database_path.stat().st_mtime_ns
        except OSError:
            return None
        key = (str(self.database_path.resolve()), stamp, context["as_of"].isoformat())
        with _RANKING_LOCK:
            if _RANKING_STATE.get("key") != key:
                try:
                    inputs = load_annotation_inputs(
                        self.database_path, context["as_of"], RANKING_CONFIG
                    )
                except Exception as exc:  # any failure means "no score", never a crash
                    LOGGER.warning("survival score unavailable: %s", exc)
                    inputs = None
                _RANKING_STATE.clear()
                _RANKING_STATE.update(key=key, inputs=inputs, notes={})
            return _RANKING_STATE["inputs"]

    def _batch_note(
        self,
        context: dict[str, Any],
        inputs: AnnotationInputs,
        units: list[dict[str, Any]],
        destination: str,
        travel_hours: float,
        settings: dict[str, Any],
    ) -> BatchAnnotation | None:
        """The annotation of one batch, cached with the inputs; None if it cannot be computed."""
        allowance = context["config"].arrival_allowance_hours
        min_days = settings["remaining_life_min_days"]["RBC"]
        key = (tuple(u["unit_id"] for u in units), destination, travel_hours, allowance, min_days)
        notes = _RANKING_STATE.get("notes", {})
        if key in notes:
            return notes[key]
        source, group = units[0]["facility_id"], units[0]["blood_group"]
        try:
            note = annotate_batch(
                pd.DataFrame(units, columns=BATCH_COLUMNS),
                destination,
                inputs.stock,
                inputs.demand,
                inputs.origin,
                travel_hours,
                inputs.routine_run_days(source, destination),
                RANKING_CONFIG,
                arrival_allowance_hours=allowance,
                min_remaining_days=min_days,
                scored=inputs.site_scores(RANKING_CONFIG, source, destination, group),
            )
        except Exception as exc:  # any failure means "no score", never a crash
            LOGGER.info("no survival score for %s: %s", key[0], exc)
            note = None
        notes[key] = note
        return note

    def _annotate(
        self,
        context: dict[str, Any],
        suggestion: Suggestion,
        units: list[dict[str, Any]],
        destination: str,
        route: tuple[float | None, str | None],
        settings: dict[str, Any],
    ) -> Suggestion:
        """Fill expected_use_*, survival_score_* and send_by from ranking.annotate.

        Eligibility has already decided that this move may be suggested; the score never adds,
        drops or reorders suggestions. If the score cannot be computed for this batch (no demand
        model for the sender, no unit history, missing route time), or its result is not a valid
        Suggestion, the suggestion is returned unchanged, with those fields left empty.
        """
        inputs = self._ranking_inputs(context)
        if inputs is None or route[0] is None:
            return suggestion
        note = self._batch_note(context, inputs, units, destination, float(route[0]), settings)
        if note is None:
            return suggestion
        try:
            update = note.as_suggestion_update(suggestion.warnings)
            if not all(math.isfinite(update[key]) for key in ANNOTATED_NUMBERS):
                return suggestion
            update["uncertainty"] = Uncertainty(**update["uncertainty"])
            update["reason_deterministic"] = (
                f"{suggestion.reason_deterministic} {update['reason_deterministic']}"
            )
            return Suggestion.model_validate({**suggestion.model_dump(), **update})
        except Exception as exc:  # any failure means "no score", never a crash
            LOGGER.info("survival fields rejected for %s: %s", suggestion.suggestion_id, exc)
            return suggestion


def clear_ranking_cache() -> None:
    """Forget the cached survival-score inputs and annotations (tests, or a forced reload)."""
    with _RANKING_LOCK:
        _RANKING_STATE.clear()


def _suggestion_id(as_of: datetime, unit_id: str) -> str:
    digest = hashlib.sha256(f"{as_of.date()}:{unit_id}".encode()).hexdigest()[:20]
    return f"sug-{digest}"
