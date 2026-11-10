"use client";

import { useState } from "react";
import { ActionDialog } from "@/components/action-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActionResult, Suggestion, SuggestionAction } from "@/lib/api/schemas";
import { useRole } from "@/lib/session";
import {
  DataAgeChip,
  ExpiryChip,
  FallbackChip,
  PolicyChip,
  WarningChip,
} from "@/components/status-chips";

function fmt(value: number | null, unit = "") {
  return value === null ? "not computed" : `${value}${unit}`;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

export function OutcomeNote({
  action,
  result,
}: {
  action: SuggestionAction;
  result: ActionResult;
}) {
  const text =
    action === "accept"
      ? "Accepted: units reserved. Waiting for the sending officer to dispatch."
      : action === "change"
        ? "Changed: a revised suggestion replaces this one."
        : "Rejected: reason recorded in the audit trail.";
  return (
    <p
      role="status"
      className={
        action === "reject"
          ? "rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground"
          : "rounded-md bg-ok px-3 py-2 text-sm text-ok-foreground"
      }
    >
      {text}
      {result.state && ` State: ${result.state}.`}
      {result.move_id && ` Move ${result.move_id}.`}
    </p>
  );
}

function SiteName({ id, name }: { id: string; name?: string }) {
  return (
    <span>
      {name ? `${name} ` : ""}
      <code className="text-sm">{id}</code>
    </span>
  );
}

export function SuggestionCard({
  suggestion: s,
  placeholder = false,
  onDecided,
}: {
  suggestion: Suggestion;
  placeholder?: boolean;
  onDecided?: (suggestion: Suggestion, action: SuggestionAction, result: ActionResult) => void;
}) {
  const unitCount = s.unit_ids.length;
  const { role } = useRole();
  const [dialog, setDialog] = useState<SuggestionAction | null>(null);
  const [outcome, setOutcome] = useState<{ action: SuggestionAction; result: ActionResult } | null>(
    null,
  );

  const blockedReason = placeholder
    ? "Placeholder card: actions need the live API."
    : role !== "coordinator"
      ? "Only the regional stock coordinator can accept, change or reject."
      : !s.eligibility_ok
        ? "This suggestion failed eligibility checks."
        : null;
  const canAct = !blockedReason && !outcome;

  return (
    <Card className={placeholder ? "border-dashed opacity-80" : undefined}>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap gap-2">
          <ExpiryChip expiryDate={s.expiry_date} asOf={s.as_of} />
          {s.fallback ? <FallbackChip /> : <PolicyChip policy={s.policy} />}
          <DataAgeChip asOf={s.as_of} ageHours={s.data_age_hours} />
        </div>
        <CardTitle className="text-lg leading-snug">
          Move {unitCount} {s.blood_group} {s.component} unit{unitCount === 1 ? "" : "s"} from{" "}
          <SiteName id={s.from_facility_id} name={s.from_facility_name} /> to{" "}
          <SiteName id={s.to_facility_id} name={s.to_facility_name} />
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        <p>{s.reason_deterministic}</p>
        {s.reason_llm && (
          <p className="text-sm text-muted-foreground">
            Plain-language version (rewritten from the same numbers): {s.reason_llm}
          </p>
        )}

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Field label="Typical travel" value={fmt(s.typical_travel_hours, " h")} />
          <Field label="Sender reserve kept" value={fmt(s.sender_reserve_units, " units")} />
          <Field label="Sender stock after" value={fmt(s.sender_stock_after, " units")} />
          <Field label="Recipient gap" value={fmt(s.recipient_gap_units, " units")} />
          <Field label="Expected use if moved (estimate)" value={fmt(s.expected_use_if_moved)} />
          <Field label="Expected use if it stays (estimate)" value={fmt(s.expected_use_if_stays)} />
        </dl>

        <p className="text-sm text-muted-foreground">
          Uncertainty: {s.uncertainty.label}
          {s.uncertainty.nominal_level !== null &&
            ` (nominal ${Math.round(s.uncertainty.nominal_level * 100)}% bound)`}
          . A model estimate, not a clinical probability.
        </p>

        {s.warnings.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {s.warnings.map((w) => (
              <WarningChip key={w}>{w}</WarningChip>
            ))}
          </div>
        )}

        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            Unit IDs ({unitCount})
          </summary>
          <ul className="mt-2 font-mono">
            {s.unit_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </details>
      </CardContent>

      <CardFooter className="flex flex-wrap items-center gap-2">
        {outcome ? (
          <OutcomeNote action={outcome.action} result={outcome.result} />
        ) : (
          <>
            <Button disabled={!canAct} onClick={() => setDialog("accept")}>
              Accept
            </Button>
            <Button variant="outline" disabled={!canAct} onClick={() => setDialog("change")}>
              Change
            </Button>
            <Button variant="outline" disabled={!canAct} onClick={() => setDialog("reject")}>
              Reject
            </Button>
            {blockedReason && (
              <span className="text-sm text-muted-foreground">{blockedReason}</span>
            )}
          </>
        )}
      </CardFooter>

      {dialog && role && (
        <ActionDialog
          suggestion={s}
          action={dialog}
          role={role}
          open
          onOpenChange={(open) => !open && setDialog(null)}
          onDone={(action, result) => {
            setOutcome({ action, result });
            onDecided?.(s, action, result);
          }}
        />
      )}
    </Card>
  );
}
