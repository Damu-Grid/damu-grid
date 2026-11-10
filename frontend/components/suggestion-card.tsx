"use client";

import Link from "next/link";
import { useState } from "react";
import { ActionDialog } from "@/components/action-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardFooter } from "@/components/ui/card";
import type { ActionResult, Suggestion, SuggestionAction } from "@/lib/api/schemas";
import { initials, shortName } from "@/lib/facilities";
import { useRole } from "@/lib/session";
import { cn } from "@/lib/utils";
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

function units(value: number | null) {
  return value === null ? "not computed" : `${value} unit${value === 1 ? "" : "s"}`;
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
      {result.move_id && (
        <>
          {" "}
          <Link href={`/moves/${encodeURIComponent(result.move_id)}`} className="underline">
            Move {result.move_id}
          </Link>
          .
        </>
      )}
    </p>
  );
}

/** Rh-negative groups are the scarce ones: gold badge, as in the reference. */
function GroupBadge({ group }: { group: string }) {
  const negative = group.endsWith("-");
  return (
    <span
      className={
        negative
          ? "rounded-md bg-gold-soft px-1.5 py-0.5 text-xs font-bold text-gold-ink"
          : "rounded-md border border-pale px-1.5 py-0.5 text-xs font-bold text-navy"
      }
    >
      {group.replace("-", "−")}
    </span>
  );
}

function daysAfterAsOf(expiryDate: string, asOf: string) {
  return Math.floor((Date.parse(`${expiryDate}T23:59:59+03:00`) - Date.parse(asOf)) / 86_400_000);
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

  const from = shortName(s.from_facility_id, s.from_facility_name);
  const to = shortName(s.to_facility_id, s.to_facility_name);
  const expiring = daysAfterAsOf(s.expiry_date, s.as_of) <= 10;

  return (
    <Card className={cn("gap-0 py-0", placeholder && "border-dashed opacity-80")}>
      <div className="flex items-start gap-3 px-5 pt-4">
        <span
          className="grid size-11 shrink-0 place-items-center rounded-full bg-navy text-xs font-bold text-white"
          aria-hidden
        >
          {initials(s.from_facility_id, s.from_facility_name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[1.05rem] font-bold text-ink">
              {from} → {to}
            </span>
            <GroupBadge group={s.blood_group} />
            {s.fallback && <FallbackChip />}
          </div>
          <div className="font-mono text-xs text-ink-2">
            {s.from_facility_id} → {s.to_facility_id}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="font-bold text-ink">
            {unitCount} unit{unitCount === 1 ? "" : "s"}
          </div>
          <div className="text-xs text-ink-2">{s.component}</div>
        </div>
      </div>
      <div
        className={cn("mx-5 mt-3 h-1.5 rounded-full", expiring ? "bg-gold" : "bg-navy")}
        title={expiring ? "Expiring soon: moving it avoids waste" : "Top-up"}
        aria-hidden
      />

      <div className="space-y-3 px-5 py-4">
        <p className="text-ink">{s.reason_deterministic}</p>
        {s.reason_llm && (
          <p className="text-sm text-ink-2">
            Plain-language version (rewritten from the same numbers): {s.reason_llm}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <ExpiryChip expiryDate={s.expiry_date} asOf={s.as_of} />
          {!s.fallback && <PolicyChip policy={s.policy} />}
          <DataAgeChip asOf={s.as_of} ageHours={s.data_age_hours} />
        </div>

        <p className="text-sm text-ink-2">
          {fmt(s.typical_travel_hours, " h")} by road · recipient gap {units(s.recipient_gap_units)} ·
          sender keeps {units(s.sender_reserve_units)}
          {s.sender_stock_after !== null && `, ${s.sender_stock_after} left after`}
        </p>

        <p className="text-sm text-ink-2">
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
          <summary className="cursor-pointer text-ink-2">
            Estimates and unit IDs ({unitCount})
          </summary>
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2">
            <Field label="Expected use if moved (estimate)" value={fmt(s.expected_use_if_moved)} />
            <Field label="Expected use if it stays (estimate)" value={fmt(s.expected_use_if_stays)} />
          </dl>
          <ul className="mt-2 font-mono">
            {s.unit_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </details>
      </div>

      <CardFooter className="flex flex-wrap items-center gap-2 px-5 pb-4">
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
