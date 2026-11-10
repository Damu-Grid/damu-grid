import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Integration run against the real prototype backend (backend/prototype.py,
// PR #50) on the official starter data. Starts it with a fresh demo database.
// PROTOTYPE_DIR: repo checkout that contains backend/prototype.py (default: this repo).
const PROTOTYPE_DIR = path.resolve(process.env.PROTOTYPE_DIR ?? "..");
const APP_PORT = 3101;

export default defineConfig({
  testDir: "./e2e-prototype",
  timeout: 90_000,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${APP_PORT}`, trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL ?? "msedge" },
    },
  ],
  webServer: [
    {
      command:
        "node -e \"require('fs').rmSync('data/processed/prototype.sqlite',{force:true})\" && python backend/prototype.py",
      cwd: PROTOTYPE_DIR,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `pnpm exec next dev --turbopack -p ${APP_PORT}`,
      url: `http://localhost:${APP_PORT}/login`,
      env: { NEXT_PUBLIC_BACKEND: "prototype", NEXT_DIST_DIR: ".next-e2e-proto" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
