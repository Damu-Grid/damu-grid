"use client";

import Link from "next/link";
import { use } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AuditTimeline, MoveCard } from "@/components/move-parts";
import { ApiError } from "@/lib/api/client";
import { useMove } from "@/lib/api/hooks";
import { stateKey } from "@/lib/api/schemas";

export default function MovePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const moveId = decodeURIComponent(id);
  const { data: move, error, isPending } = useMove(moveId);
  const apiError = error instanceof ApiError ? error : null;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/queue" className="text-sm underline">
          ← Review queue
        </Link>
        <h1 className="text-2xl font-semibold">Move {moveId}</h1>
      </div>

      {apiError && (
        <Alert variant="destructive">
          <AlertTitle>Could not load this move</AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      )}
      {isPending && <p className="text-muted-foreground">Loading…</p>}

      {move && (
        <>
          {stateKey(move.state) === "receivedheld" && (
            <Alert>
              <AlertTitle>Held for safety review</AlertTitle>
              <AlertDescription>
                Cold-chain evidence was missing or out of range. Only the safety officer can clear
                these units. Damu Grid never clears a hold on its own.
              </AlertDescription>
            </Alert>
          )}
          <MoveCard move={move} />
          <section aria-labelledby="audit-heading" className="space-y-3">
            <h2 id="audit-heading" className="text-lg font-semibold">
              Audit trail
            </h2>
            <AuditTimeline events={move.audit} />
          </section>
        </>
      )}
    </div>
  );
}
