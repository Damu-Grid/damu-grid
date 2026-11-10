// Facility names and positions from the official starter data (synthetic,
// generic names). Regenerate with `pnpm build:facilities`.
import data from "./facilities.json";

export type Facility = (typeof data)[number];

const BY_ID = new Map<string, Facility>(data.map((f) => [f.id, f]));

export const FACILITIES: readonly Facility[] = data;

export function facility(id: string): Facility | undefined {
  return BY_ID.get(id);
}

// Suffixes dropped for the short label; centres keep a type hint so towns with
// both a centre and a hospital (e.g. Kisumu) stay distinguishable.
const SUFFIXES: [RegExp, string][] = [
  [/ Regional Blood Transfusion Centre$/, " RBTC"],
  [/ Satellite Blood Centre$/, " satellite"],
  [/^National Referral Hospital \((.+)\)$/, "National Referral, $1"],
  [/ (Teaching and Referral|County Referral|Sub-County|County|Level 5|Private|Mission) Hospital$/, ""],
  [/ Maternity Hospital$/, " Maternity"],
];

/** Short display name, e.g. "Migori", "Kisumu RBTC"; falls back to the ID. */
export function shortName(id: string, apiName?: string | null): string {
  const name = apiName ?? facility(id)?.name;
  if (!name) return id;
  return SUFFIXES.reduce((n, [re, to]) => n.replace(re, to), name);
}

/** Up to three letters for the avatar, e.g. "MIG", "KSM". */
export function initials(id: string, apiName?: string | null): string {
  const name = shortName(id, apiName);
  if (name === id) return id.split("-").pop()!.slice(0, 3).toUpperCase();
  return name.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}
