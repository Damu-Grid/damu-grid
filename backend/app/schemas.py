from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BloodGroup = Literal["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
Policy = Literal["expiry_aware", "nearest", "fallback"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductScope(StrictModel):
    component: Literal["RBC"] = "RBC"
    blood_groups: list[BloodGroup] = Field(
        default_factory=lambda: ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
    )


class SnapshotResponse(BaseModel):
    data_ready: bool
    as_of: datetime | None
    table_counts: dict[str, int] | None
    product_scope: ProductScope = Field(default_factory=ProductScope)


class Uncertainty(BaseModel):
    method: str
    nominal_level: float | None = None
    label: str


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_id: str
    as_of: datetime
    data_age_hours: float | None
    component: str
    blood_group: BloodGroup
    unit_ids: list[str] = Field(min_length=1)
    unit_version: int = Field(default=0, ge=0)
    from_facility_id: str
    to_facility_id: str
    from_facility_name: str | None = None
    to_facility_name: str | None = None
    expiry_date: date
    send_by: date | None = None
    typical_travel_hours: float | None
    sender_reserve_units: int | None
    sender_stock_after: int | None
    recipient_gap_units: int | None
    expected_use_if_moved: float | None = None
    expected_use_if_stays: float | None = None
    survival_score_if_moved: float | None = None
    survival_score_if_stays: float | None = None
    uncertainty: Uncertainty
    reason_deterministic: str
    reason_llm: str | None = None
    explanation_source: Literal["llm", "template"] = "template"
    explanation_model: str | None = None
    latency_ms: int | None = None
    policy: Policy
    fallback: bool
    eligibility_ok: bool
    warnings: list[str] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def as_of_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone offset")
        return value

    @field_validator("unit_ids")
    @classmethod
    def unit_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("unit_ids must be unique")
        return value


class SuggestionListResponse(BaseModel):
    items: list[Suggestion]


class DecisionRequest(StrictModel):
    event_id: str
    actor_id: str
    role: str
    reason: str
    unit_version: int


class ChangeRequest(DecisionRequest):
    unit_ids: list[str]
    to_facility_id: str


class MoveActionRequest(StrictModel):
    event_id: str
    actor_id: str
    role: str
    reason: str = ""


class ReceiveRequest(MoveActionRequest):
    cold_chain_evidence_complete: bool = False


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    actor_id: str | None
    move_id: str | None
    unit_id: str | None
    payload: dict


class SettingsUpdateRequest(StrictModel):
    event_id: str
    actor_id: str
    role: str
    settings: dict


class AlertSimulationRequest(StrictModel):
    event_id: str
    actor_id: str
    role: str
    recipient_role: str
    message: str = Field(max_length=320)


class SyncEvent(StrictModel):
    event_id: str
    action: Literal["accept", "change", "reject", "dispatch", "receive"]
    resource_id: str
    actor_id: str
    role: str
    payload: dict = Field(default_factory=dict)


class SyncQueueRequest(StrictModel):
    events: list[SyncEvent]
