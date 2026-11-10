import { defineConfig, devices } from "@playwright/test";

const MOCK_API_PORT = 8765;
const APP_PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${APP_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // Uses the installed Microsoft Edge locally (no browser download). On CI,
      // set PW_CHANNEL=chromium after `playwright install chromium`.
      use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL ?? "msedge" },
    },
  ],
  webServer: [
    {
      command: `node e2e/mock-api.mjs`,
      url: `http://localhost:${MOCK_API_PORT}/health`,
      env: { MOCK_API_PORT: String(MOCK_API_PORT) },
      reuseExistingServer: false,
    },
    {
      command: `pnpm exec next dev --turbopack -p ${APP_PORT}`,
      url: `http://localhost:${APP_PORT}/login`,
      env: {
        NEXT_PUBLIC_API_BASE_URL: `http://localhost:${MOCK_API_PORT}`,
        NEXT_DIST_DIR: ".next-e2e", // never touch the developer's running `.next`
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
