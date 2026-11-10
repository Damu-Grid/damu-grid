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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, newEventId } from "@/lib/api/client";
import { useSuggestionAction } from "@/lib/api/hooks";
import {
  REJECT_REASONS,
  type ActionResult,
  type Role,
  type Suggestion,
  type SuggestionAction,
} from "@/lib/api/schemas";
import { DEMO_ACTORS } from "@/lib/session";

const COPY: Record<SuggestionAction, { title: string; verb: string; help: string }> = {
  accept: {
    title: "Accept this transfer",
    verb: "Accept and reserve",
    help: "Accepting reserves these units for this move. It is not dispatch, and it is not a release for transfusion.",
  },
  change: {
    title: "Change this transfer",
    verb: "Submit change",
    help: "A change cancels any reservation and creates a revised suggestion. Eligibility is checked again.",
  },
  reject: {
    title: "Reject this transfer",
    verb: "Reject",
    help: "Nothing is reserved. Your reason is recorded in the audit trail.",
  },
};

const MIN_REASON = 3;

export function ActionDialog({
  suggestion: s,
  action,
  role,
  open,
  onOpenChange,
  onDone,
}: {
  suggestion: Suggestion;
  action: SuggestionAction;
  role: Role;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: (action: SuggestionAction, result: ActionResult) => void;
}) {
  const mutation = useSuggestionAction();
  // One idempotency key per decision: a retry after a network error reuses it.
  const [eventId, setEventId] = useState(newEventId);
  const [reason, setReason] = useState("");
  const [rejectPreset, setRejectPreset] = useState<string>("");
  const [toFacility, setToFacility] = useState(s.to_facility_id);
  const [unitIds, setUnitIds] = useState<string[]>(s.unit_ids);

  const copy = COPY[action];
  const fullReason =
    action === "reject" && rejectPreset
      ? [rejectPreset, reason.trim()].filter(Boolean).join(": ")
      : reason.trim();
  const changed =
    toFacility.trim() !== s.to_facility_id || unitIds.length !== s.unit_ids.length;
  const canSubmit =
    !mutation.isPending &&
    (action === "reject" ? rejectPreset !== "" : reason.trim().length >= MIN_REASON) &&
    (action !== "change" || (changed && unitIds.length > 0 && toFacility.trim() !== ""));

  function reset() {
    setEventId(newEventId());
    setReason("");
    setRejectPreset("");
    setToFacility(s.to_facility_id);
    setUnitIds(s.unit_ids);
    mutation.reset();
  }

  function submit() {
    if (!canSubmit) return;
    mutation.mutate(
      {
        suggestion: s,
        action,
        input: {
          event_id: eventId,
          actor_id: DEMO_ACTORS[role].actorId,
          role,
          reason: fullReason,
          ...(action === "change" && {
            to_facility_id: toFacility.trim(),
            unit_ids: unitIds,
          }),
        },
      },
      {
        onSuccess: (result) => {
          toast.success(
            action === "accept"
              ? "Accepted. Units reserved for this move."
              : action === "change"
                ? "Change submitted. A revised suggestion was created."
                : "Rejected. Reason recorded.",
          );
          onDone(action, result);
          onOpenChange(false);
          reset();
        },
        onError: (error) => {
          // A 409 means this decision is stale: the next attempt is a new decision.
          if (error instanceof ApiError && error.status === 409) setEventId(newEventId());
        },
      },
    );
  }

  const error = mutation.error instanceof ApiError ? mutation.error : null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) reset();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{copy.title}</DialogTitle>
            <DialogDescription>
              {s.unit_ids.length} {s.blood_group} {s.component} unit
              {s.unit_ids.length === 1 ? "" : "s"}, {s.from_facility_id} → {s.to_facility_id}.{" "}
              {copy.help}
            </DialogDescription>
          </DialogHeader>

          {action === "change" && (
            <fieldset className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="to-facility">Destination facility ID</Label>
                <input
                  id="to-facility"
                  value={toFacility}
                  onChange={(e) => setToFacility(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
                  autoComplete="off"
                />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Units to move</p>
                <ul className="max-h-40 space-y-1 overflow-auto rounded-md border p-2">
                  {s.unit_ids.map((id) => (
                    <li key={id}>
                      <label className="flex items-center gap-2 font-mono text-sm">
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={unitIds.includes(id)}
                          onChange={(e) =>
                            setUnitIds((prev) =>
                              e.target.checked ? [...prev, id] : prev.filter((u) => u !== id),
                            )
                          }
                        />
                        {id}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
              {!changed && (
                <p className="text-sm text-muted-foreground">
                  Change the destination or leave out at least one unit.
                </p>
              )}
            </fieldset>
          )}

          {action === "reject" && (
            <div className="space-y-1">
              <Label htmlFor="reject-reason">Reason</Label>
              <Select value={rejectPreset} onValueChange={setRejectPreset}>
                <SelectTrigger id="reject-reason" className="w-full">
                  <SelectValue placeholder="Pick a reason" />
                </SelectTrigger>
                <SelectContent>
                  {REJECT_REASONS.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-1">
            <Label htmlFor="action-note">
              {action === "reject" ? "Note (optional)" : "Reason (required)"}
            </Label>
            <Textarea
              id="action-note"
              autoFocus={action !== "reject"}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={
                action === "accept"
                  ? "e.g. Recipient confirmed it can receive today"
                  : action === "change"
                    ? "e.g. Closer hospital has the same gap"
                    : "Anything the team should know"
              }
            />
            <p className="text-xs text-muted-foreground">Ctrl+Enter to submit.</p>
          </div>

          {error && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>
                {error.status === 409
                  ? "Conflict: this suggestion changed"
                  : error.status === 403
                    ? "Not allowed"
                    : error.status === 422
                      ? "Failed eligibility checks"
                      : error.status === 503
                        ? "Not available on the server yet"
                        : "Could not submit"}
              </AlertTitle>
              <AlertDescription>
                {error.message}
                {error.status === 409 && " The queue has been reloaded."}
              </AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              variant={action === "reject" ? "destructive" : "default"}
            >
              {mutation.isPending ? "Submitting…" : copy.verb}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
