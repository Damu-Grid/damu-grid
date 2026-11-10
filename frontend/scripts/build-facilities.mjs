// Builds lib/facilities.json from the official starter data (data/raw/facilities.csv)
// so the UI can show facility names and positions when an API sends only IDs.
// Synthetic data: generic names, not real facilities. Run: pnpm build:facilities
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const csv = readFileSync(join(here, "../../data/raw/facilities.csv"), "utf8").trim().split(/\r?\n/);
const header = csv[0].split(",");
const col = (name) => {
  const i = header.indexOf(name);
  if (i < 0) throw new Error(`facilities.csv has no column ${name}`);
  return i;
};
const [id, name, type, county, lat, lon, conn] = [
  "facility_id", "name", "facility_type", "county", "lat", "lon", "connectivity",
].map(col);

const facilities = csv.slice(1).map((line) => {
  const c = line.split(",");
  return {
    id: c[id],
    name: c[name],
    type: c[type],
    county: c[county],
    lat: Number(c[lat]),
    lon: Number(c[lon]),
    connectivity: c[conn],
  };
});
writeFileSync(join(here, "../lib/facilities.json"), JSON.stringify(facilities, null, 1) + "\n");
console.log(`lib/facilities.json: ${facilities.length} facilities`);
