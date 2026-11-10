"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, newEventId } from "@/lib/api/client";
import { useMoveAction } from "@/lib/api/hooks";
import type { ColdChainEvidence, Move, MoveAction, Role } from "@/lib/api/schemas";
import { DEMO_ACTORS } from "@/lib/session";

const DISPATCH_CHECKS = [
  "I have the physical units and the unit IDs match the pick list",
  "Units are packed in a validated cool box",
  "No new quarantine or exposure flag is shown on these units",
];

const EVIDENCE: { value: ColdChainEvidence; label: string; help: string }[] = [
  { value: "ok", label: "Cool box stayed in range", help: "Maximum cool-box temperature at or below 10 °C." },
  { value: "excursion", label: "Cool box went out of range", help: "Units will be held for the safety officer." },
  { value: "unknown", label: "Not sure / no evidence", help: "Units will be held for the safety officer." },
];

export function MoveActionDialog({
  move: m,
  action,
  role,
  open,
  onOpenChange,
}: {
  move: Move;
  action: MoveAction;
  role: Role;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useMoveAction();
  const [eventId, setEventId] = useState(newEventId);
  const [checks, setChecks] = useState<boolean[]>(DISPATCH_CHECKS.map(() => false));
  const [evidence, setEvidence] = useState<ColdChainEvidence | null>(null);
  const [maxTemp, setMaxTemp] = useState("");
  const [note, setNote] = useState("");

  const tempValue = maxTemp.trim() === "" ? null : Number(maxTemp);
  const tempInvalid = tempValue !== null && !Number.isFinite(tempValue);
  const canSubmit =
    !mutation.isPending &&
    (action === "dispatch" ? checks.every(Boolean) : evidence !== null && !tempInvalid);

  function submit() {
    if (!canSubmit) return;
    mutation.mutate(
      {
        move: m,
        action,
        input: {
          event_id: eventId,
          actor_id: DEMO_ACTORS[role].actorId,
          role,
          note: note.trim() || undefined,
          ...(action === "receive" && {
            cold_chain_evidence: evidence ?? "unknown",
            coolbox_max_temp_c: tempValue,
          }),
        },
      },
      {
        onSuccess: (updated) => {
          toast.success(
            action === "dispatch"
              ? "Dispatched. The receiving officer can now confirm arrival."
              : `Receipt recorded.${updated.state ? ` State: ${updated.state}.` : ""}`,
          );
          onOpenChange(false);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) setEventId(newEventId());
        },
      },
    );
  }

  const error = mutation.error instanceof ApiError ? mutation.error : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{action === "dispatch" ? "Recheck and dispatch" : "Confirm receipt"}</DialogTitle>
            <DialogDescription>
              {m.unit_ids.length} {m.blood_group} {m.component}, {m.from_facility_id} →{" "}
              {m.to_facility_id}.{" "}
              {action === "dispatch"
                ? "The server rechecks safety, the lease and the arrival time before accepting."
                : "Receipt adds the units to your stock. It is not a release for transfusion."}
            </DialogDescription>
          </DialogHeader>

          {action === "dispatch" ? (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Before dispatch</legend>
              {DISPATCH_CHECKS.map((c, i) => (
                <label key={c} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4"
                    checked={checks[i]}
                    onChange={(e) =>
                      setChecks((prev) => prev.map((v, j) => (j === i ? e.target.checked : v)))
                    }
                  />
                  {c}
                </label>
              ))}
            </fieldset>
          ) : (
            <>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Cold-chain evidence</legend>
                {EVIDENCE.map((o) => (
                  <label key={o.value} className="flex items-start gap-2 text-sm">
                    <input
                      type="radio"
                      name="evidence"
                      className="mt-0.5 size-4"
                      checked={evidence === o.value}
                      onChange={() => setEvidence(o.value)}
                    />
                    <span>
                      <strong>{o.label}.</strong> {o.help}
                    </span>
                  </label>
                ))}
              </fieldset>
              <div className="space-y-1">
                <Label htmlFor="max-temp">Cool-box maximum temperature, °C (optional)</Label>
                <input
                  id="max-temp"
                  inputMode="decimal"
                  value={maxTemp}
                  onChange={(e) => setMaxTemp(e.target.value)}
                  className="w-32 rounded-md border bg-background px-3 py-2 text-sm"
                  aria-invalid={tempInvalid}
                />
                {tempInvalid && <p className="text-sm text-destructive">Enter a number, e.g. 6.5</p>}
              </div>
            </>
          )}

          <div className="space-y-1">
            <Label htmlFor="move-note">Note (optional)</Label>
            <Textarea id="move-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          {error && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>
                {error.status === 409
                  ? "Conflict: this move changed"
                  : error.status === 403
                    ? "Not allowed"
                    : error.status === 422
                      ? "Blocked by the safety recheck"
                      : "Could not submit"}
              </AlertTitle>
              <AlertDescription>{error.message}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {mutation.isPending
                ? "Submitting…"
                : action === "dispatch"
                  ? "Confirm dispatch"
                  : "Confirm receipt"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
