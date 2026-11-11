"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { SyntheticBadge } from "@/components/status-chips";
import { ApiError } from "@/lib/api/client";
import { useMoves, useSuggestions } from "@/lib/api/hooks";

const NEAR_EXPIRY_DAYS = 7;

/** Whole days from as-of to expiry, same convention as the ExpiryChip. */
function daysToExpiry(expiryDate: string, asOf: string): number | null {
  const ms = Date.parse(`${expiryDate}T23:59:59+03:00`) - Date.parse(asOf);
  return Number.isFinite(ms) ? Math.floor(ms / 86_400_000) : null;
}

export default function AlertsPage() {
  const suggestions = useSuggestions("expiry_aware");
  const heldMoves = useMoves(["quarantined"]);
  const list = suggestions.data ?? [];
  const asOf = suggestions.data?.[0]?.as_of ?? new Date().toISOString();

  const shortages = list.filter((s) => (s.recipient_gap_units ?? 0) > 0);
  const nearExpiry = list.filter((s) => {
    const days = daysToExpiry(s.expiry_date, asOf);
    return days !== null && days >= 0 && days <= NEAR_EXPIRY_DAYS;
  });
  const holds = heldMoves.data ?? [];
  const holdsUnavailable = heldMoves.error instanceof ApiError;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Alerts</h1>
          <p className="text-muted-foreground">
            Shortages, units near expiry, and cold-chain holds from the live backend. Synthetic data.
          </p>
        </div>
        <SyntheticBadge />
      </div>

      {suggestions.error && !suggestions.data && (
        <Alert variant="destructive">
          <AlertTitle>Could not load suggestions</AlertTitle>
          <AlertDescription>{(suggestions.error as Error).message}</AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="alerts-shortage">
        <h2 id="alerts-shortage" className="text-lg font-semibold">
          Shortages ({shortages.length})
        </h2>
        {shortages.length === 0 ? (
          <p className="text-muted-foreground">No recipient gaps in the current suggestions.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {shortages.map((s) => (
              <li key={s.suggestion_id} className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-sm">
                <span>
                  {s.to_facility_name} ({s.to_facility_id})
                </span>
                <span>
                  needs {s.recipient_gap_units} {s.blood_group} unit{s.recipient_gap_units === 1 ? "" : "s"}
                </span>
                <span className="text-muted-foreground">
                  proposed from {s.from_facility_name}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="alerts-expiry">
        <h2 id="alerts-expiry" className="text-lg font-semibold">
          Units expiring within {NEAR_EXPIRY_DAYS} days ({nearExpiry.length})
        </h2>
        {nearExpiry.length === 0 ? (
          <p className="text-muted-foreground">No suggested units near expiry right now.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {nearExpiry.map((s) => (
              <li key={s.suggestion_id} className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-sm">
                <span>
                  {s.unit_ids.length} × {s.blood_group} at {s.from_facility_name}
                </span>
                <span>expires {s.expiry_date}</span>
                {s.send_by && <span className="text-muted-foreground">send by {s.send_by}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="alerts-coldchain">
        <h2 id="alerts-coldchain" className="text-lg font-semibold">
          Cold-chain holds ({holdsUnavailable ? "unavailable" : holds.length})
        </h2>
        {holdsUnavailable ? (
          <p className="text-muted-foreground">
            The backend does not expose a holds list to this client yet — quarantine decisions are
            recorded in the audit trail instead.
          </p>
        ) : holds.length === 0 ? (
          <p className="text-muted-foreground">No quarantined moves right now.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {holds.map((m) => (
              <li key={m.move_id} className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-sm">
                <span>
                  Move <code>{m.move_id}</code>
                </span>
                <span className="text-muted-foreground">{m.state}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
