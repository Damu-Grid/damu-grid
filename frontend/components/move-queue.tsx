"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { MoveActionDialog } from "@/components/move-action-dialog";
import { PageHeader } from "@/components/page-header";
import { LeaseNote, MoveCard, useLeaseMinutesLeft } from "@/components/move-parts";
import { ApiError } from "@/lib/api/client";
import { useMoves } from "@/lib/api/hooks";
import { stateKey, type Move, type MoveAction, type Role } from "@/lib/api/schemas";
import { DEMO_ACTORS, useRole } from "@/lib/session";

const CONFIG: Record<
  MoveAction,
  { role: Role; states: string[]; button: string; empty: string }
> = {
  dispatch: {
    role: "sender",
    states: ["reserved"],
    button: "Recheck and dispatch",
    empty: "No reserved moves waiting for dispatch.",
  },
  receive: {
    role: "receiver",
    states: ["dispatched", "in_transit"],
    button: "Confirm receipt",
    empty: "No moves in transit to you.",
  },
};

function MoveRow({ move, action, role }: { move: Move; action: MoveAction; role: Role | null }) {
  const [open, setOpen] = useState(false);
  const cfg = CONFIG[action];
  const minutesLeft = useLeaseMinutesLeft(action === "dispatch" ? move.lease_expires_at : null);
  const blocked =
    role !== cfg.role
      ? `Only the ${DEMO_ACTORS[cfg.role].title.toLowerCase()} can do this.`
      : action === "dispatch" && minutesLeft !== null && minutesLeft < 0
        ? "Lease expired. The coordinator must accept again."
        : action === "dispatch" && stateKey(move.state) !== "reserved"
          ? "Only reserved moves can be dispatched."
          : null;

  return (
    <MoveCard move={move}>
      <Button disabled={!!blocked} onClick={() => setOpen(true)}>
        {cfg.button}
      </Button>
      <LeaseNote minutesLeft={minutesLeft} />
      {blocked && <span className="text-sm text-muted-foreground">{blocked}</span>}
      {open && role && (
        <MoveActionDialog move={move} action={action} role={role} open onOpenChange={setOpen} />
      )}
    </MoveCard>
  );
}

export function MoveQueue({ action, title, intro }: { action: MoveAction; title: string; intro: React.ReactNode }) {
  const { role } = useRole();
  const { data, error, isPending } = useMoves(CONFIG[action].states);
  const apiError = error instanceof ApiError ? error : null;

  return (
    <div className="space-y-6">
      <PageHeader title={title}>{intro}</PageHeader>

      {apiError && (
        <Alert variant={apiError.status === 0 || apiError.status === 404 ? "default" : "destructive"}>
          <AlertTitle>
            {apiError.status === 0 || apiError.status === 404
              ? "Moves are not available from the API yet"
              : "Could not load moves"}
          </AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      )}

      {isPending && <p className="text-muted-foreground">Loading moves…</p>}
      {data && data.length === 0 && <p className="text-muted-foreground">{CONFIG[action].empty}</p>}
      {data && data.length > 0 && (
        <ul className="space-y-4">
          {data.map((m) => (
            <li key={m.move_id}>
              <MoveRow move={m} action={action} role={role} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
