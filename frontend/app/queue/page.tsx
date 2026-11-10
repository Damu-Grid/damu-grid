"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/page-header";
import { PlaceholderBanner } from "@/components/placeholder-banner";
import { OutcomeNote, SuggestionCard } from "@/components/suggestion-card";
import { ApiError } from "@/lib/api/client";
import { useSuggestions } from "@/lib/api/hooks";
import type { ActionResult, Suggestion, SuggestionAction } from "@/lib/api/schemas";
import { FIXTURE_SUGGESTIONS } from "@/lib/fixtures/suggestions";

type Decision = { suggestion: Suggestion; action: SuggestionAction; result: ActionResult };

export default function QueuePage() {
  const [modelOff, setModelOff] = useState(false);
  // Decided suggestions usually leave the queue on reload; keep the outcome visible.
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const policy = modelOff ? "fallback" : "expiry_aware";
  const { data, error, isPending, refetch, isFetching } = useSuggestions(policy);

  const apiError = error instanceof ApiError ? error : null;
  const estimatorDown = apiError?.status === 503;
  // Placeholders only when the API itself is missing, never to cover a real error.
  const showPlaceholders = !!apiError && (apiError.status === 0 || apiError.status === 404);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Review queue"
        actions={
          <div className="flex items-center gap-4 rounded-2xl border border-white/90 bg-card px-3 py-2 shadow-card">
            <div className="flex items-center gap-2">
              <Switch id="model-off" checked={modelOff} onCheckedChange={setModelOff} />
              <Label htmlFor="model-off">Model off (fallback rule)</Label>
            </div>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              {isFetching ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        }
      >
        <p>
          Suggested red cell transfers. <b>Damu Grid suggests; a person decides every move.</b>
        </p>
      </PageHeader>

      {estimatorDown && !modelOff && (
        <Alert>
          <AlertTitle>The demand estimator is offline</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-3">
            The fallback rule (nearest eligible site) still works with the same safety checks.
            <Button size="sm" onClick={() => setModelOff(true)}>
              Use the fallback rule
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {apiError && !showPlaceholders && !estimatorDown && (
        <Alert variant="destructive">
          <AlertTitle>Could not load suggestions</AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      )}

      {decisions.length > 0 && (
        <section aria-labelledby="decisions-heading" className="space-y-2">
          <h2 id="decisions-heading" className="text-lg font-semibold">
            Decisions this session
          </h2>
          <ul className="space-y-2">
            {decisions.map((d) => (
              <li key={`${d.suggestion.suggestion_id}-${d.action}`} className="space-y-1">
                <p className="text-sm">
                  {d.suggestion.unit_ids.length} {d.suggestion.blood_group}{" "}
                  {d.suggestion.component}, <code>{d.suggestion.from_facility_id}</code> →{" "}
                  <code>{d.suggestion.to_facility_id}</code>
                </p>
                <OutcomeNote action={d.action} result={d.result} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {isPending && <p className="text-muted-foreground">Loading suggestions…</p>}

      {showPlaceholders && (
        <>
          <PlaceholderBanner reason={apiError.message} />
          <ul className="space-y-4">
            {FIXTURE_SUGGESTIONS.filter((s) => s.fallback === modelOff).map((s) => (
              <li key={s.suggestion_id}>
                <SuggestionCard suggestion={s} placeholder />
              </li>
            ))}
          </ul>
        </>
      )}

      {data && data.length === 0 && (
        <p className="text-muted-foreground">
          No eligible transfers for this snapshot. That can be a correct answer.
        </p>
      )}

      {data && data.length > 0 && (
        <ul className="space-y-4">
          {data.map((s) => (
            <li key={s.suggestion_id}>
              <SuggestionCard
                suggestion={s}
                onDecided={(suggestion, action, result) =>
                  setDecisions((prev) => [{ suggestion, action, result }, ...prev])
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
