"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PlaceholderBanner } from "@/components/placeholder-banner";
import { SyntheticBadge } from "@/components/status-chips";
import { ApiError } from "@/lib/api/client";
import { useSnapshot, useSuggestions } from "@/lib/api/hooks";
import { FIXTURE_SUGGESTIONS } from "@/lib/fixtures/suggestions";
import { buildMapData, RISK_LABEL, type FacilityRisk } from "@/lib/map/risks";
import { cn } from "@/lib/utils";

const DOT_FILL: Record<FacilityRisk, string> = {
  shortage: "fill-destructive",
  expiry: "fill-warn-foreground",
  steady: "fill-brand",
  unknown: "fill-muted",
};

const LEGEND_DOT: Record<FacilityRisk, string> = {
  shortage: "bg-destructive",
  expiry: "bg-expiry-foreground",
  steady: "bg-brand",
  unknown: "bg-muted",
};

export default function MapPage() {
  const {
    data: suggestions,
    error,
    isPending,
    refetch,
    isFetching,
  } = useSuggestions("expiry_aware");
  const { data: snapshot } = useSnapshot();

  const apiError = error instanceof ApiError ? error : null;
  const showPlaceholders = !!apiError && (apiError.status === 0 || apiError.status === 404);
  const list = showPlaceholders ? FIXTURE_SUGGESTIONS.filter((s) => !s.fallback) : (suggestions ?? []);
  const asOf = snapshot?.as_of ?? list[0]?.as_of ?? null;
  const { nodes, edges, unmapped } = buildMapData(list, asOf ?? new Date().toISOString());
  const shown = nodes.filter((n) => n.risk !== "unknown");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Transfer map</h1>
          <p className="text-muted-foreground">
            Facilities coloured by review need, with suggested transfer lines. Synthetic data.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SyntheticBadge />
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
      </div>

      {apiError && !showPlaceholders && (
        <Alert variant="destructive">
          <AlertTitle>Could not load suggestions</AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      )}
      {showPlaceholders && <PlaceholderBanner reason={apiError.message} />}
      {isPending && <p className="text-muted-foreground">Loading map…</p>}

      {!isPending && (
        <>
          <section aria-label="Map summary" className="flex flex-wrap gap-2 text-sm">
            {(Object.keys(RISK_LABEL) as FacilityRisk[]).map((risk) => (
              <span
                key={risk}
                className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1"
              >
                <span aria-hidden className={cn("inline-block h-2.5 w-2.5 rounded-full", LEGEND_DOT[risk])} />
                {RISK_LABEL[risk]}: {nodes.filter((n) => n.risk === risk).length}
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1">
              Transfer lines: {edges.length}
            </span>
          </section>

          <svg
            viewBox="-8 -8 416 316"
            role="img"
            aria-label={`Schematic Kenya map with ${shown.length} facilities and ${edges.length} suggested transfers`}
            className="w-full rounded-md border bg-card"
          >
            {edges.map((e) => (
              <line
                key={`${e.from}-${e.to}`}
                x1={e.x1}
                y1={e.y1}
                x2={e.x2}
                y2={e.y2}
                className="stroke-brand"
                strokeWidth={Math.min(3, 0.75 + e.units / 4)}
                strokeOpacity={0.55}
              >
                <title>
                  {e.from} → {e.to}: {e.units} unit{e.units === 1 ? "" : "s"}
                </title>
              </line>
            ))}
            {nodes.map((n) => (
              <circle key={n.facility_id} cx={n.x} cy={n.y} r={n.risk === "unknown" ? 2.5 : 4} className={DOT_FILL[n.risk]}>
                <title>
                  {n.name} ({n.facility_id}): {RISK_LABEL[n.risk]}
                  {n.inboundGap > 0 && `, gap ${n.inboundGap}`}
                  {n.outboundUnits > 0 && `, ${n.outboundUnits} outgoing`}
                </title>
              </circle>
            ))}
          </svg>
          {unmapped > 0 && (
            <p className="text-sm text-muted-foreground">
              {unmapped} suggestion{unmapped === 1 ? "" : "s"} reference facilit{unmapped === 1 ? "y" : "ies"} outside the
              coordinate list and {unmapped === 1 ? "is" : "are"} not drawn.
            </p>
          )}

          <section aria-labelledby="map-table-heading">
            <h2 id="map-table-heading" className="text-lg font-semibold">
              Facilities on this map
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th scope="col" className="py-2 pr-4">Facility</th>
                    <th scope="col" className="py-2 pr-4">Type</th>
                    <th scope="col" className="py-2 pr-4">Need</th>
                    <th scope="col" className="py-2 pr-4">Incoming gap</th>
                    <th scope="col" className="py-2">Outgoing units</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((n) => (
                    <tr key={n.facility_id} className="border-b">
                      <td className="py-2 pr-4">
                        {n.name} <code className="text-muted-foreground">{n.facility_id}</code>
                      </td>
                      <td className="py-2 pr-4">{n.facility_type.replaceAll("_", " ")}</td>
                      <td className="py-2 pr-4">{RISK_LABEL[n.risk]}</td>
                      <td className="py-2 pr-4">{n.inboundGap}</td>
                      <td className="py-2">{n.outboundUnits}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
