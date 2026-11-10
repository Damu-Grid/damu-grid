import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.explanations import ExplanationService, default_explanation_service
from backend.app.ranking import SQLiteSuggestionProvider
from backend.app.schemas import (
    AlertSimulationRequest,
    AuditEvent,
    ChangeRequest,
    DecisionRequest,
    MoveActionRequest,
    Policy,
    ReceiveRequest,
    SettingsUpdateRequest,
    SnapshotResponse,
    Suggestion,
    SuggestionListResponse,
    SyncQueueRequest,
)
from backend.app.services import (
    SuggestionProvider,
    SuggestionServiceUnavailable,
    read_snapshot_summary,
)
from backend.app.state import ActionError, ActionStore, ChangeSuggestion, EligibilityCheck

EAT = timezone(timedelta(hours=3))


def _configured_as_of() -> datetime | None:
    raw_date = os.getenv("AS_OF_DATE", "2026-10-31")
    try:
        as_of_date = date.fromisoformat(raw_date)
    except ValueError:
        return None
    return datetime.combine(as_of_date, time(23, 59, 59), tzinfo=EAT)


def _database_path() -> Path:
    raw_url = os.getenv("DATABASE_URL", "sqlite:///./data/processed/damu_grid.sqlite")
    prefix = "sqlite:///"
    if not raw_url.startswith(prefix):
        raise RuntimeError("Only a local SQLite DATABASE_URL is supported in this demo.")
    path = raw_url[len(prefix) :]
    return Path(path)


def _action_database_path() -> Path:
    raw_url = os.getenv("ACTION_DATABASE_URL", "sqlite:///./data/processed/actions.sqlite")
    prefix = "sqlite:///"
    if not raw_url.startswith(prefix):
        raise RuntimeError("Only a local SQLite ACTION_DATABASE_URL is supported in this demo.")
    return Path(raw_url[len(prefix) :])


def _api_error(exc: ActionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


def create_app(
    *,
    database_path: Path | None = None,
    suggestion_provider: SuggestionProvider | None = None,
    explanation_service: ExplanationService | None = None,
    action_database_path: Path | None = None,
    eligibility_check: EligibilityCheck | None = None,
    change_suggestion: ChangeSuggestion | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Damu Grid API",
        description=(
            "Synthetic stock-coordination review API. Suggestions require human review; "
            "this API does not release units for transfusion."
        ),
        version="0.1.0",
    )
    store_path = database_path
    action_store_path = action_database_path or (
        _action_database_path()
        if database_path is None
        else database_path.with_name("actions.sqlite")
    )
    explainer = explanation_service or default_explanation_service(str(action_store_path))
    actions = ActionStore(
        action_store_path,
        lease_minutes=int(os.getenv("RESERVATION_LEASE_MINUTES", "30")),
    )
    app.state.action_store = actions
    active_provider = suggestion_provider
    active_eligibility_check = eligibility_check
    active_change_suggestion = change_suggestion
    if active_provider is None:
        def ranker() -> SQLiteSuggestionProvider:
            return SQLiteSuggestionProvider(store_path or _database_path(), _configured_as_of())

        def provide_suggestions(policy: str) -> list[Suggestion]:
            return ranker().suggest(
                policy,
                actions.get_settings(),
                actions.unavailable_unit_ids(),
                actions.pending_inbound_units(),
            )

        def check_eligibility(
            suggestion: Suggestion, connection: sqlite3.Connection
        ) -> bool:
            excluded = actions.unavailable_unit_ids(connection) - set(suggestion.unit_ids)
            pending = actions.pending_inbound_units(suggestion.suggestion_id, connection)
            return ranker().is_eligible(
                suggestion,
                actions.get_settings(connection),
                excluded,
                pending,
            )

        def change_recommendation(
            original: Suggestion,
            unit_ids: list[str],
            destination: str,
            connection: sqlite3.Connection,
        ) -> Suggestion:
            excluded = actions.unavailable_unit_ids(connection) - set(original.unit_ids)
            pending = actions.pending_inbound_units(original.suggestion_id, connection)
            try:
                return ranker().change(
                    original,
                    unit_ids,
                    destination,
                    actions.get_settings(connection),
                    excluded,
                    pending,
                )
            except ValueError as exc:
                raise ActionError(422, "eligibility_failed", str(exc)) from exc

        active_provider = provide_suggestions
        active_eligibility_check = active_eligibility_check or check_eligibility
        active_change_suggestion = active_change_suggestion or change_recommendation

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/snapshot", response_model=SnapshotResponse, tags=["system"])
    def snapshot() -> SnapshotResponse:
        path = store_path or _database_path()
        ready, counts = read_snapshot_summary(path)
        return SnapshotResponse(
            data_ready=ready,
            as_of=_configured_as_of() if ready else None,
            table_counts=counts,
        )

    @app.get("/suggestions", response_model=SuggestionListResponse, tags=["suggestions"])
    def suggestions(
        policy: Annotated[Policy, Query()] = "expiry_aware",
    ) -> SuggestionListResponse:
        try:
            items = actions.save_suggestions(active_provider(policy))
            items = explainer.apply_many(items, budget_seconds=8.0)
            is_fallback = policy == "fallback"
            items = [
                item.model_copy(update={"policy": policy, "fallback": is_fallback})
                for item in items
            ]
            return SuggestionListResponse(items=actions.save_suggestions(items))
        except SuggestionServiceUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "code": "suggestions_not_ready",
                    "message": str(exc),
                },
            )

    @app.post("/suggestions/{suggestion_id}/accept", tags=["actions"])
    def accept(suggestion_id: str, body: DecisionRequest) -> dict:
        try:
            return actions.decide(
                suggestion_id=suggestion_id,
                decision="accept",
                body=body.model_dump(),
                checker=active_eligibility_check,
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/suggestions/{suggestion_id}/reject", tags=["actions"])
    def reject(suggestion_id: str, body: DecisionRequest) -> dict:
        try:
            return actions.decide(
                suggestion_id=suggestion_id,
                decision="reject",
                body=body.model_dump(),
                checker=active_eligibility_check,
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.get("/suggestions/{suggestion_id}", response_model=Suggestion, tags=["suggestions"])
    def get_suggestion(suggestion_id: str) -> Suggestion:
        try:
            return actions.read_suggestion(suggestion_id)
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/suggestions/{suggestion_id}/change", tags=["actions"])
    def change(suggestion_id: str, body: ChangeRequest) -> dict:
        try:
            return actions.change(
                suggestion_id=suggestion_id,
                body=body.model_dump(),
                checker=active_eligibility_check,
                change_suggestion=active_change_suggestion,
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/moves/{move_id}/dispatch", tags=["moves"])
    def dispatch(move_id: str, body: MoveActionRequest) -> dict:
        try:
            return actions.transition(
                move_id=move_id,
                action="dispatch",
                body=body.model_dump(),
                checker=active_eligibility_check,
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/moves/{move_id}/receive", tags=["moves"])
    def receive(move_id: str, body: ReceiveRequest) -> dict:
        try:
            return actions.transition(
                move_id=move_id,
                action="receive",
                body=body.model_dump(),
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/moves/{move_id}/quarantine", tags=["moves"])
    def quarantine(move_id: str, body: MoveActionRequest) -> dict:
        try:
            return actions.transition(
                move_id=move_id,
                action="quarantine",
                body=body.model_dump(),
            )
        except ActionError as exc:
            return _api_error(exc)

    @app.get("/moves/{move_id}", tags=["moves"])
    def get_move(move_id: str) -> dict:
        try:
            move = actions.get_move(move_id)
        except ActionError as exc:
            return _api_error(exc)
        move["audit"] = actions.list_audit({"move_id": move_id})
        return move

    @app.get("/audit", response_model=list[AuditEvent], tags=["audit"])
    def get_audit(
        unit_id: str | None = None,
        move_id: str | None = None,
        actor_id: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> list[dict]:
        return actions.list_audit(
            {
                "unit_id": unit_id,
                "move_id": move_id,
                "actor_id": actor_id,
                "from_time": from_time,
                "to_time": to_time,
            }
        )

    @app.get("/settings", tags=["settings"])
    def get_settings() -> dict:
        return {"settings": actions.get_settings()}

    @app.put("/settings", tags=["settings"])
    def put_settings(body: SettingsUpdateRequest) -> dict:
        try:
            return actions.update_settings(body.model_dump())
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/alerts/simulate", tags=["alerts"])
    def simulate_alert(body: AlertSimulationRequest) -> dict:
        try:
            return actions.simulate_alert(body.model_dump())
        except ActionError as exc:
            return _api_error(exc)

    @app.post("/sync/queue", tags=["sync"])
    def sync_queue(body: SyncQueueRequest) -> dict:
        results = []
        for event in body.events:
            try:
                event_payload = event.model_dump(mode="json")
                pending = actions.set_sync_status(event.event_id, event_payload, "pending", {})
                if pending["status"] != "pending":
                    results.append(pending)
                    continue
                action_body = {
                    **event.payload,
                    "event_id": event.event_id,
                    "actor_id": event.actor_id,
                    "role": event.role,
                }
                try:
                    if event.action in {"accept", "reject"}:
                        request = DecisionRequest.model_validate(action_body)
                        result = actions.decide(
                            suggestion_id=event.resource_id,
                            decision=event.action,
                            body=request.model_dump(),
                            checker=eligibility_check,
                        )
                    elif event.action == "change":
                        request = ChangeRequest.model_validate(action_body)
                        result = actions.change(
                            suggestion_id=event.resource_id,
                            body=request.model_dump(),
                            checker=eligibility_check,
                            change_suggestion=change_suggestion,
                        )
                    elif event.action == "dispatch":
                        request = MoveActionRequest.model_validate(action_body)
                        result = actions.transition(
                            move_id=event.resource_id,
                            action="dispatch",
                            body=request.model_dump(),
                            checker=eligibility_check,
                        )
                    else:
                        request = ReceiveRequest.model_validate(action_body)
                        result = actions.transition(
                            move_id=event.resource_id,
                            action="receive",
                            body=request.model_dump(),
                        )
                    status = "accepted"
                except ActionError as exc:
                    result = {"code": exc.code, "message": exc.message}
                    status = "rejected_on_reconcile"
                except ValidationError:
                    result = {
                        "code": "invalid_pending_action",
                        "message": "Pending action payload is invalid.",
                    }
                    status = "rejected_on_reconcile"
                results.append(
                    actions.set_sync_status(event.event_id, event_payload, status, result)
                )
            except (sqlite3.OperationalError, TimeoutError, ConnectionError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "sync_temporarily_unavailable",
                        "message": "Pending action reconciliation can be retried.",
                    },
                ) from exc
        return {"items": results}

    @app.get("/sync/status", tags=["sync"])
    def sync_status(event_ids: list[str] | None = None) -> dict:
        return {"items": actions.list_sync_status(event_ids)}

    return app


app = create_app()
