// Pure aggregation for the transfer map: no DOM, no fetching, easy to reason about.
import type { Suggestion } from "@/lib/api/schemas";
import { MAP_FACILITIES, type MapFacility } from "./facilities";

export type FacilityRisk = "shortage" | "expiry" | "steady" | "unknown";

export type FacilityNode = MapFacility & {
  risk: FacilityRisk;
  inboundGap: number;
  outboundUnits: number;
  soonestExpiry: string | null;
  x: number;
  y: number;
};

export type TransferEdge = {
  from: string;
  to: string;
  units: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

const W = 400;
const H = 300;
const LONS = MAP_FACILITIES.map((f) => f.lon);
const LATS = MAP_FACILITIES.map((f) => f.lat);
const MIN_LON = Math.min(...LONS);
const MAX_LON = Math.max(...LONS);
const MIN_LAT = Math.min(...LATS);
const MAX_LAT = Math.max(...LATS);

export function project(lon: number, lat: number): { x: number; y: number } {
  return {
    x: ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * W,
    y: ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * H,
  };
}

/** Days from as-of to expiry, same convention as the ExpiryChip. */
function daysToExpiry(expiryDate: string, asOf: string): number | null {
  const ms = Date.parse(`${expiryDate}T23:59:59+03:00`) - Date.parse(asOf);
  return Number.isFinite(ms) ? Math.floor(ms / 86_400_000) : null;
}

/** Outgoing units expiring within this many days flag a facility as expiry-risk. */
export const EXPIRY_RISK_DAYS = 10;

export function buildMapData(suggestions: Suggestion[], asOf: string): {
  nodes: FacilityNode[];
  edges: TransferEdge[];
  unmapped: number;
} {
  const byId = new Map(MAP_FACILITIES.map((f) => [f.facility_id, f]));
  const gap = new Map<string, number>();
  const outbound = new Map<string, { units: number; soonest: string | null }>();
  const pairs = new Map<string, { from: string; to: string; units: number }>();
  let unmapped = 0;

  for (const s of suggestions) {
    if (!byId.has(s.from_facility_id) || !byId.has(s.to_facility_id)) {
      unmapped += 1;
      continue;
    }
    gap.set(s.to_facility_id, (gap.get(s.to_facility_id) ?? 0) + (s.recipient_gap_units ?? 0));
    const out = outbound.get(s.from_facility_id) ?? { units: 0, soonest: null };
    out.units += s.unit_ids.length;
    if (out.soonest === null || s.expiry_date < out.soonest) out.soonest = s.expiry_date;
    outbound.set(s.from_facility_id, out);
    const key = `${s.from_facility_id}|${s.to_facility_id}`;
    const edge = pairs.get(key) ?? { from: s.from_facility_id, to: s.to_facility_id, units: 0 };
    edge.units += s.unit_ids.length;
    pairs.set(key, edge);
  }

  const nodes: FacilityNode[] = MAP_FACILITIES.map((f) => {
    const inboundGap = gap.get(f.facility_id) ?? 0;
    const out = outbound.get(f.facility_id);
    const days = out?.soonest ? daysToExpiry(out.soonest, asOf) : null;
    const risk: FacilityRisk =
      inboundGap > 0
        ? "shortage"
        : days !== null && days <= EXPIRY_RISK_DAYS
          ? "expiry"
          : out
            ? "steady"
            : "unknown";
    const { x, y } = project(f.lon, f.lat);
    return {
      ...f,
      risk,
      inboundGap,
      outboundUnits: out?.units ?? 0,
      soonestExpiry: out?.soonest ?? null,
      x,
      y,
    };
  });

  const edges: TransferEdge[] = [...pairs.values()].map((e) => {
    const a = project(byId.get(e.from)!.lon, byId.get(e.from)!.lat);
    const b = project(byId.get(e.to)!.lon, byId.get(e.to)!.lat);
    return { ...e, x1: a.x, y1: a.y, x2: b.x, y2: b.y };
  });

  return { nodes, edges, unmapped };
}

export const RISK_LABEL: Record<FacilityRisk, string> = {
  shortage: "Shortage (incoming gap)",
  expiry: "Surplus near expiry (outgoing expires within 10 days)",
  steady: "Steady",
  unknown: "No suggestion data",
};
