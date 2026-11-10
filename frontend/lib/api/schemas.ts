// Mirrors docs/API_SPEC.md. When the backend publishes /openapi.json, these
// should be checked against it; the API spec is the contract, not this file.
import { z } from "zod";

export const BLOOD_GROUPS = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"] as const;
export const ROLES = ["coordinator", "sender", "receiver", "safety"] as const;
export const POLICIES = ["expiry_aware", "nearest", "fallback"] as const;

export const RoleSchema = z.enum(ROLES);
export type Role = z.infer<typeof RoleSchema>;

export const PolicySchema = z.enum(POLICIES);
export type Policy = z.infer<typeof PolicySchema>;

export const UncertaintySchema = z.object({
  method: z.string(),
  nominal_level: z.number().nullable(),
  label: z.string(),
});

export const SuggestionSchema = z.object({
  suggestion_id: z.string(),
  as_of: z.string(),
  data_age_hours: z.number().nullable(),
  component: z.string(),
  blood_group: z.string(),
  unit_ids: z.array(z.string()),
  from_facility_id: z.string(),
  to_facility_id: z.string(),
  // Facility names are not in the spec yet; shown when the API provides them.
  from_facility_name: z.string().optional(),
  to_facility_name: z.string().optional(),
  expiry_date: z.string(),
  typical_travel_hours: z.number().nullable(),
  sender_reserve_units: z.number().nullable(),
  sender_stock_after: z.number().nullable(),
  recipient_gap_units: z.number().nullable(),
  expected_use_if_moved: z.number().nullable(),
  expected_use_if_stays: z.number().nullable(),
  uncertainty: UncertaintySchema,
  reason_deterministic: z.string(),
  reason_llm: z.string().nullable(),
  policy: PolicySchema,
  fallback: z.boolean(),
  eligibility_ok: z.boolean(),
  warnings: z.array(z.string()),
});
export type Suggestion = z.infer<typeof SuggestionSchema>;

// The list shape is not fixed in the spec yet: accept a bare array or {items: [...]}.
export const SuggestionListSchema = z
  .union([z.array(SuggestionSchema), z.object({ items: z.array(SuggestionSchema) })])
  .transform((v) => (Array.isArray(v) ? v : v.items));

// Coordinator actions (docs/API_SPEC.md): bodies carry actor_id, role, reason,
// an event_id for idempotency and, when known, a unit_version. Server sets time.
export const ACTIONS = ["accept", "change", "reject"] as const;
export type SuggestionAction = (typeof ACTIONS)[number];

export const REJECT_REASONS = [
  "Not enough staff or transport",
  "Receiving hospital refused",
  "Data looks wrong",
  "Other",
] as const;

export type ActionBody = {
  event_id: string;
  actor_id: string;
  role: Role;
  reason: string;
  unit_version?: number;
  // Change only: a revised destination and/or a subset of the units.
  to_facility_id?: string;
  unit_ids?: string[];
};

// The response shape is not fixed in the spec yet; keep what the API sends.
export const ActionResultSchema = z
  .object({
    state: z.string().optional(),
    move_id: z.string().optional(),
    suggestion_id: z.string().optional(),
    suggestion: SuggestionSchema.optional(),
  })
  .passthrough();
export type ActionResult = z.infer<typeof ActionResultSchema>;

// Moves follow the state machine in docs/ARCHITECTURE.md. State names are
// compared case-insensitively without separators ("InTransit" == "in_transit").
export const AuditEventSchema = z
  .object({
    event_id: z.string().optional(),
    ts: z.string(),
    actor_id: z.string(),
    role: z.string(),
    action: z.string(),
    from_state: z.string().nullable().optional(),
    to_state: z.string().nullable().optional(),
    reason: z.string().nullable().optional(),
  })
  .passthrough();
export type AuditEvent = z.infer<typeof AuditEventSchema>;

export const MoveSchema = z
  .object({
    move_id: z.string(),
    suggestion_id: z.string().optional(),
    state: z.string(),
    version: z.number().optional(),
    component: z.string(),
    blood_group: z.string(),
    unit_ids: z.array(z.string()),
    from_facility_id: z.string(),
    to_facility_id: z.string(),
    expiry_date: z.string().optional(),
    typical_travel_hours: z.number().nullable().optional(),
    lease_expires_at: z.string().nullable().optional(),
    warnings: z.array(z.string()).default([]),
    audit: z.array(AuditEventSchema).default([]),
  })
  .passthrough();
export type Move = z.infer<typeof MoveSchema>;

export const MoveListSchema = z
  .union([z.array(MoveSchema), z.object({ items: z.array(MoveSchema) })])
  .transform((v) => (Array.isArray(v) ? v : v.items));

export const MOVE_ACTIONS = ["dispatch", "receive"] as const;
export type MoveAction = (typeof MOVE_ACTIONS)[number];

// What the receiving officer can say about the cool-box evidence. Anything but
// "ok" must leave the units held for the safety officer; receipt never clears it.
export const COLD_CHAIN_EVIDENCE = ["ok", "excursion", "unknown"] as const;
export type ColdChainEvidence = (typeof COLD_CHAIN_EVIDENCE)[number];

export type MoveActionBody = {
  event_id: string;
  actor_id: string;
  role: Role;
  version?: number;
  note?: string;
  // Receive only.
  cold_chain_evidence?: ColdChainEvidence;
  coolbox_max_temp_c?: number | null;
};

export function stateKey(state: string): string {
  return state.toLowerCase().replace(/[^a-z]/g, "");
}

// GET /evaluation/forecast (docs/EVALUATION.md): frozen 28-day baseline vs the
// pooled candidate. RMSE is primary; MAE, n and coverage are shown beside it.
export const EvalRowSchema = z
  .object({
    model: z.string(), // e.g. "baseline_28d", "pooled_candidate"
    label: z.string().optional(),
    horizon_days: z.number(),
    group: z.string().default("all"), // "all" or a blood group such as "O-"
    rmse: z.number().nullable(),
    mae: z.number().nullable(),
    n: z.number().nullable(),
    coverage: z.number().nullable().optional(),
    nominal_level: z.number().nullable().optional(),
  })
  .passthrough();
export type EvalRow = z.infer<typeof EvalRowSchema>;

export const ForecastEvalSchema = z
  .object({
    computed_at: z.string().optional(),
    split: z
      .object({
        learn: z.tuple([z.string(), z.string()]).optional(),
        calibrate: z.tuple([z.string(), z.string()]).optional(),
        evaluate: z.tuple([z.string(), z.string()]).optional(),
      })
      .partial()
      .optional(),
    rows: z.array(EvalRowSchema),
    excluded_unknown_group_rows: z.number().optional(),
    operational_model: z.string().optional(),
    notes: z.array(z.string()).default([]),
  })
  .passthrough();
export type ForecastEval = z.infer<typeof ForecastEvalSchema>;

export const SnapshotSchema = z
  .object({
    as_of: z.string(),
    product_scope: z.unknown().optional(),
    counts: z.record(z.string(), z.number()).optional(),
  })
  .passthrough();
export type Snapshot = z.infer<typeof SnapshotSchema>;

export const ApiErrorBodySchema = z
  .object({
    code: z.string().optional(),
    message: z.string().optional(),
    detail: z.unknown().optional(),
  })
  .passthrough();
