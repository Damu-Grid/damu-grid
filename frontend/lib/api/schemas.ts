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

export const SnapshotSchema = z
  .object({
    as_of: z.string(),
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
