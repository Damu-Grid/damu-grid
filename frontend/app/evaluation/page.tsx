"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SyntheticBadge } from "@/components/status-chips";
import { ApiError } from "@/lib/api/client";
import { useForecastEval, useSnapshot } from "@/lib/api/hooks";
import type { EvalRow, ForecastEval } from "@/lib/api/schemas";

const MODEL_LABELS: Record<string, string> = {
  baseline_28d: "28-day average (baseline)",
  pooled_candidate: "Pooled estimator (candidate)",
};

const isBaseline = (r: EvalRow) => r.model.startsWith("baseline");
const modelLabel = (r: EvalRow) => r.label ?? MODEL_LABELS[r.model] ?? r.model;
const num = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

/** Headline: 7-day horizon (or the longest available), all known groups. */
function headline(data: ForecastEval) {
  const all = data.rows.filter((r) => r.group === "all" && r.rmse !== null);
  const horizon = all.some((r) => r.horizon_days === 7)
    ? 7
    : Math.max(...all.map((r) => r.horizon_days));
  const base = all.find((r) => r.horizon_days === horizon && isBaseline(r));
  const cand = all.find((r) => r.horizon_days === horizon && !isBaseline(r));
  if (!base || !cand || base.rmse === null || cand.rmse === null || base.rmse === 0) return null;
  const change = ((cand.rmse - base.rmse) / base.rmse) * 100;
  return { horizon, base, cand, change, candidateWins: cand.rmse < base.rmse };
}

function Verdict({ data }: { data: ForecastEval }) {
  const h = headline(data);
  if (!h)
    return (
      <p className="text-muted-foreground">
        Both models are needed at the same horizon to compare them.
      </p>
    );
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-lg">
        {h.horizon}-day demand forecast error (RMSE, requested red cell units):{" "}
        <strong>candidate {num(h.cand.rmse)}</strong> vs{" "}
        <strong>baseline {num(h.base.rmse)}</strong>
        {h.candidateWins
          ? `, ${Math.abs(h.change).toFixed(1)}% lower.`
          : `, ${Math.abs(h.change).toFixed(1)}% higher.`}
      </p>
      <p className="mt-1">
        {h.candidateWins
          ? "The candidate beat the baseline on held-out weeks."
          : "The candidate did not beat the baseline. The live queue uses the baseline."}
        {data.operational_model && ` Used in the live queue: ${data.operational_model}.`}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Synthetic starter data, retrospective test. Not evidence about real facilities, and not
        units of blood saved.
      </p>
    </div>
  );
}

function ResultsTable({ rows }: { rows: EvalRow[] }) {
  const sorted = [...rows].sort(
    (a, b) =>
      (a.group === "all" ? -1 : 1) - (b.group === "all" ? -1 : 1) ||
      a.group.localeCompare(b.group) ||
      a.horizon_days - b.horizon_days ||
      Number(!isBaseline(a)) - Number(!isBaseline(b)),
  );
  const lowest = new Map<string, number>();
  for (const r of rows) {
    const k = `${r.group}|${r.horizon_days}`;
    if (r.rmse !== null) lowest.set(k, Math.min(lowest.get(k) ?? Infinity, r.rmse));
  }
  return (
    <Table>
      <TableCaption>
        RMSE and MAE in requested units per hospital, blood group and forecast origin. Lower is
        better.
      </TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Groups</TableHead>
          <TableHead>Horizon</TableHead>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">RMSE</TableHead>
          <TableHead className="text-right">MAE</TableHead>
          <TableHead className="text-right">n</TableHead>
          <TableHead className="text-right">Upper-bound coverage</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => {
          const best = r.rmse !== null && r.rmse === lowest.get(`${r.group}|${r.horizon_days}`);
          return (
            <TableRow key={`${r.group}|${r.horizon_days}|${r.model}`}>
              <TableCell>{r.group === "all" ? "All known groups" : r.group}</TableCell>
              <TableCell>{r.horizon_days} d</TableCell>
              <TableCell>{modelLabel(r)}</TableCell>
              <TableCell className="text-right font-medium">
                {num(r.rmse)}
                {best && <span className="ml-1 text-xs text-ok-foreground">(lower)</span>}
              </TableCell>
              <TableCell className="text-right">{num(r.mae)}</TableCell>
              <TableCell className="text-right">{r.n ?? "—"}</TableCell>
              <TableCell className="text-right">
                {r.coverage == null
                  ? "—"
                  : `${(r.coverage * 100).toFixed(1)}%${
                      r.nominal_level != null
                        ? ` (nominal ${Math.round(r.nominal_level * 100)}%)`
                        : ""
                    }`}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function Method({ data }: { data: ForecastEval }) {
  const range = (r?: [string, string]) => (r ? `${r[0]} to ${r[1]}` : "not stated");
  return (
    <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
      <dt className="text-muted-foreground">Demand</dt>
      <dd>Requested red cell units (requests.units_requested), hospitals, known blood groups</dd>
      <dt className="text-muted-foreground">Learn</dt>
      <dd>{range(data.split?.learn)}</dd>
      <dt className="text-muted-foreground">Calibrate</dt>
      <dd>{range(data.split?.calibrate)}</dd>
      <dt className="text-muted-foreground">Evaluate (weekly origins)</dt>
      <dd>{range(data.split?.evaluate)}</dd>
      {data.excluded_unknown_group_rows !== undefined && (
        <>
          <dt className="text-muted-foreground">Excluded</dt>
          <dd>{data.excluded_unknown_group_rows} request rows with unknown blood group</dd>
        </>
      )}
      {data.computed_at && (
        <>
          <dt className="text-muted-foreground">Computed</dt>
          <dd>{data.computed_at}</dd>
        </>
      )}
      {data.notes.map((n) => (
        <dd key={n} className="sm:col-start-2">
          {n}
        </dd>
      ))}
    </dl>
  );
}

function SnapshotSummary() {
  const { data, error } = useSnapshot();
  // Counts are shown only when the API provides them (DG-33: match /snapshot or omit).
  if (error || !data) return null;
  return (
    <section aria-labelledby="snapshot-heading" className="space-y-2">
      <h2 id="snapshot-heading" className="text-lg font-semibold">
        Stock snapshot
      </h2>
      <p className="text-sm">
        Live queue built from stock as of <strong>{data.as_of}</strong>.
      </p>
      {data.counts && (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(data.counts).map(([k, v]) => (
            <div key={k} className="rounded-md border p-3">
              <dt className="text-xs text-muted-foreground">{k.replaceAll("_", " ")}</dt>
              <dd className="text-xl font-semibold">{v.toLocaleString("en-GB")}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export default function EvaluationPage() {
  const { data, error, isPending } = useForecastEval();
  const apiError = error instanceof ApiError ? error : null;
  const notReady = apiError && (apiError.status === 0 || apiError.status === 404);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Forecast vs baseline</h1>
          <p className="text-muted-foreground">
            The demand forecast behind recipient gaps and sender reserves, tested against a
            28-day average.
          </p>
        </div>
        <SyntheticBadge />
      </div>

      {isPending && <p className="text-muted-foreground">Loading results…</p>}

      {notReady && (
        <Alert>
          <AlertTitle>Not computed yet</AlertTitle>
          <AlertDescription>
            The frozen evaluation is not available from the API yet ({apiError.message}). No
            numbers are shown until it is computed from the starter data.
          </AlertDescription>
        </Alert>
      )}
      {apiError && !notReady && (
        <Alert variant="destructive">
          <AlertTitle>Could not load the evaluation</AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      )}

      {data && data.rows.length === 0 && (
        <p className="text-muted-foreground">The API returned no evaluation rows.</p>
      )}

      {data && data.rows.length > 0 && (
        <>
          <Verdict data={data} />
          <section aria-labelledby="results-heading" className="space-y-2">
            <h2 id="results-heading" className="text-lg font-semibold">
              All results
            </h2>
            <ResultsTable rows={data.rows} />
          </section>
          <section aria-labelledby="method-heading" className="space-y-2">
            <h2 id="method-heading" className="text-lg font-semibold">
              Method
            </h2>
            <Method data={data} />
          </section>
        </>
      )}

      <SnapshotSummary />
    </div>
  );
}
