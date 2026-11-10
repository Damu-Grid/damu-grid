// Layout placeholders ONLY. Not computed, not from the starter data.
// IDs are deliberately fake (FIXTURE-...) so a screenshot can never pass as a
// real suggestion. Never use these in the recorded demo (docs/DESIGN.md).
import { SuggestionSchema, type Suggestion } from "@/lib/api/schemas";

const base = {
  as_of: "2026-10-31T23:59:59+03:00",
  data_age_hours: null,
  component: "RBC",
  reason_llm: null,
  eligibility_ok: true,
  expected_use_if_moved: null,
  expected_use_if_stays: null,
  uncertainty: {
    method: "placeholder",
    nominal_level: null,
    label: "Placeholder: no estimate computed",
  },
} as const;

const raw: Suggestion[] = [
  {
    ...base,
    suggestion_id: "FIXTURE-1",
    blood_group: "O+",
    unit_ids: ["FIXTURE-UNIT-001", "FIXTURE-UNIT-002", "FIXTURE-UNIT-003"],
    from_facility_id: "FIXTURE-SITE-A",
    to_facility_id: "FIXTURE-SITE-B",
    expiry_date: "2026-11-05",
    typical_travel_hours: null,
    sender_reserve_units: null,
    sender_stock_after: null,
    recipient_gap_units: null,
    reason_deterministic: "Layout placeholder. Not computed from the starter data.",
    policy: "expiry_aware",
    fallback: false,
    warnings: [],
  },
  {
    ...base,
    suggestion_id: "FIXTURE-2",
    blood_group: "A-",
    unit_ids: ["FIXTURE-UNIT-004"],
    from_facility_id: "FIXTURE-SITE-C",
    to_facility_id: "FIXTURE-SITE-D",
    expiry_date: "2026-11-02",
    typical_travel_hours: null,
    sender_reserve_units: null,
    sender_stock_after: null,
    recipient_gap_units: null,
    reason_deterministic: "Layout placeholder showing a warning state. Not computed.",
    policy: "expiry_aware",
    fallback: false,
    warnings: ["Placeholder warning: short remaining shelf life on arrival"],
  },
  {
    ...base,
    suggestion_id: "FIXTURE-3",
    blood_group: "B+",
    unit_ids: ["FIXTURE-UNIT-005", "FIXTURE-UNIT-006"],
    from_facility_id: "FIXTURE-SITE-E",
    to_facility_id: "FIXTURE-SITE-F",
    expiry_date: "2026-11-12",
    typical_travel_hours: null,
    sender_reserve_units: null,
    sender_stock_after: null,
    recipient_gap_units: null,
    reason_deterministic: "Layout placeholder for a fallback-rule card. Not computed.",
    policy: "fallback",
    fallback: true,
    warnings: [],
  },
];

// Fail loudly if the placeholders drift from the API contract.
export const FIXTURE_SUGGESTIONS: Suggestion[] = raw.map((s) => SuggestionSchema.parse(s));
