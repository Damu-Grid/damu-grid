"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { WarningChip } from "@/components/status-chips";
import { stateKey, type AuditEvent, type Move } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

const STATE_LABELS: Record<string, { label: string; tone: string }> = {
  suggested: { label: "Suggested", tone: "bg-secondary text-secondary-foreground" },
  reserved: { label: "Reserved", tone: "bg-warn text-warn-foreground" },
  dispatched: { label: "Dispatched", tone: "bg-secondary text-secondary-foreground" },
  intransit: { label: "In transit", tone: "bg-secondary text-secondary-foreground" },
  received: { label: "Received", tone: "bg-ok text-ok-foreground" },
  receivedheld: { label: "Received, held for safety review", tone: "bg-expiry text-expiry-foreground" },
  quarantined: { label: "Quarantined", tone: "bg-expiry text-expiry-foreground" },
  blocked: { label: "Blocked", tone: "bg-expiry text-expiry-foreground" },
  cancelled: { label: "Cancelled", tone: "bg-muted text-muted-foreground" },
  rejected: { label: "Rejected", tone: "bg-muted text-muted-foreground" },
};

export function StateBadge({ state }: { state: string }) {
  const s = STATE_LABELS[stateKey(state)] ?? { label: state, tone: "bg-muted text-muted-foreground" };
  return (
    <span className={cn("inline-flex rounded-md px-2 py-0.5 text-xs font-semibold", s.tone)}>
      {s.label}
    </span>
  );
}

function useNow(intervalMs = 15_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** Minutes left on the reservation lease; null when the API gives no lease. */
export function useLeaseMinutesLeft(leaseExpiresAt: string | null | undefined) {
  const now = useNow();
  if (!leaseExpiresAt) return null;
  return Math.floor((Date.parse(leaseExpiresAt) - now) / 60_000);
}

export function LeaseNote({ minutesLeft }: { minutesLeft: number | null }) {
  if (minutesLeft === null) return null;
  return minutesLeft < 0 ? (
    <WarningChip>Reservation lease expired: this move cannot be dispatched</WarningChip>
  ) : (
    <span className="text-sm text-muted-foreground">Lease: {minutesLeft} min left</span>
  );
}

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: "Africa/Nairobi",
    dateStyle: "short",
    timeStyle: "short",
  });

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (events.length === 0)
    return <p className="text-sm text-muted-foreground">No audit events returned yet.</p>;
  return (
    <ol className="space-y-3 border-l pl-4" aria-label="Audit trail">
      {events.map((e, i) => (
        <li key={e.event_id ?? i} className="text-sm">
          <p>
            <time className="font-mono text-xs text-muted-foreground">{fmtTime(e.ts)} EAT</time>{" "}
            <strong>{e.action}</strong> by {e.actor_id} ({e.role})
          </p>
          {(e.from_state || e.to_state) && (
            <p className="text-muted-foreground">
              {e.from_state ?? "?"} → {e.to_state ?? "?"}
            </p>
          )}
          {e.reason && <p>Reason: {e.reason}</p>}
        </li>
      ))}
    </ol>
  );
}

export function MoveCard({ move: m, children }: { move: Move; children?: React.ReactNode }) {
  const n = m.unit_ids.length;
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge state={m.state} />
          {m.expiry_date && (
            <span className="text-sm text-muted-foreground">Expires {m.expiry_date}</span>
          )}
          {m.typical_travel_hours != null && (
            <span className="text-sm text-muted-foreground">
              Typical travel {m.typical_travel_hours} h
            </span>
          )}
        </div>
        <CardTitle className="text-lg leading-snug">
          {n} {m.blood_group} {m.component} unit{n === 1 ? "" : "s"}:{" "}
          <code className="text-sm">{m.from_facility_id}</code> →{" "}
          <code className="text-sm">{m.to_facility_id}</code>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {m.warnings.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {m.warnings.map((w) => (
              <WarningChip key={w}>{w}</WarningChip>
            ))}
          </div>
        )}
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">Unit IDs ({n})</summary>
          <ul className="mt-2 font-mono">
            {m.unit_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </details>
        <Link href={`/moves/${encodeURIComponent(m.move_id)}`} className="text-sm underline">
          Move {m.move_id}: state and audit trail
        </Link>
      </CardContent>
      {children && <CardFooter className="flex flex-wrap items-center gap-2">{children}</CardFooter>}
    </Card>
  );
}
