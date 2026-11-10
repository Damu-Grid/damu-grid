import { expect, test, type Page } from "@playwright/test";

const MOCK_API = "http://localhost:8765";

// Test data only. These numbers are invented to exercise the layout.
function evalBody(candidateRmse: number) {
  return {
    computed_at: "2026-11-11T02:00:00+03:00",
    split: {
      learn: ["2025-11-01", "2026-04-30"],
      calibrate: ["2026-05-01", "2026-06-30"],
      evaluate: ["2026-07-01", "2026-10-21"],
    },
    rows: [
      { model: "baseline_28d", horizon_days: 7, group: "all", rmse: 3.0, mae: 2.0, n: 1200 },
      {
        model: "pooled_candidate",
        horizon_days: 7,
        group: "all",
        rmse: candidateRmse,
        mae: 1.9,
        n: 1200,
        coverage: 0.95,
        nominal_level: 0.95,
      },
      { model: "baseline_28d", horizon_days: 7, group: "O-", rmse: 0.9, mae: 0.5, n: 140 },
      { model: "pooled_candidate", horizon_days: 7, group: "O-", rmse: 0.8, mae: 0.4, n: 140 },
    ],
    excluded_unknown_group_rows: 42,
    notes: [],
  };
}

async function serveEval(page: Page, status: number, body: unknown) {
  await page.route(`${MOCK_API}/evaluation/forecast`, (route) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("candidate that beats the baseline", async ({ page }) => {
  await serveEval(page, 200, evalBody(2.4));
  await page.goto("/evaluation");
  await expect(page.getByText("The candidate beat the baseline")).toBeVisible();
  await expect(page.getByText("20.0% lower")).toBeVisible();
  const table = page.getByRole("table");
  await expect(table).toContainText("Pooled estimator (candidate)");
  await expect(table).toContainText("28-day average (baseline)");
  await expect(table).toContainText("1200");
  await expect(table).toContainText("95.0% (nominal 95%)");
  await expect(page.getByText("2025-11-01 to 2026-04-30")).toBeVisible();
  await expect(page.getByText("42 request rows with unknown blood group")).toBeVisible();
});

test("candidate that loses is reported honestly", async ({ page }) => {
  await serveEval(page, 200, evalBody(3.3));
  await page.goto("/evaluation");
  await expect(
    page.getByText("The candidate did not beat the baseline. The live queue uses the baseline."),
  ).toBeVisible();
  await expect(page.getByText("10.0% higher")).toBeVisible();
  // Both models still appear.
  await expect(page.getByRole("table")).toContainText("Pooled estimator (candidate)");
});

// Same shape as data/processed/forecast_metrics.json from `python -m forecasting.evaluate`.
// Test data only.
const metricsFile = {
  metrics: {
    overall: {
      baseline: { rmse: 3.0, mae: 2.0, bias: 0.1, n: 1000 },
      candidate: { rmse: 2.5, mae: 1.8, bias: 0.0, n: 1000 },
    },
    o_negative: {
      baseline: { rmse: 0.9, mae: 0.5, bias: 0.0, n: 100 },
      candidate: { rmse: 0.8, mae: 0.4, bias: 0.0, n: 100 },
    },
    rmse_reduction_pct: 16.7,
    candidate_wins: true,
    observations: { rows: 1000, origins: 17, hospitals: 32, groups: 8 },
    upper_bound: {
      method: "scaled one-sided residual bound",
      nominal_level: 0.9,
      overall: { covered: 880, n: 1000, rate: 0.88 },
      o_negative: { covered: 92, n: 100, rate: 0.92 },
      note: "Synthetic retrospective coverage; not a clinical probability",
    },
  },
  exclusions: { request_rows_total: 5000, unknown_or_missing_group: 7 },
};

test("reads the forecasting module's metrics file as served", async ({ page }) => {
  await serveEval(page, 200, metricsFile);
  await page.goto("/evaluation");
  await expect(page.getByText("The candidate beat the baseline")).toBeVisible();
  await expect(page.getByText("16.7% lower")).toBeVisible();
  const table = page.getByRole("table");
  await expect(table).toContainText("88.0% (nominal 90%)");
  await expect(table).toContainText("O-");
  await expect(page.getByText("7 request rows with unknown blood group")).toBeVisible();
  await expect(page.getByText("32 hospitals × 8 groups × 17 weekly origins")).toBeVisible();
  await expect(page.getByText("Learn", { exact: true })).toHaveCount(0); // no split in the file
});

test("no numbers before the evaluation exists", async ({ page }) => {
  await serveEval(page, 404, { code: "not_found", message: "Not computed" });
  await page.goto("/evaluation");
  await expect(page.getByText("Not computed yet")).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});
