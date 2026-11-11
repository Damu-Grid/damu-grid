import { expect, test, type Page } from "@playwright/test";

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

test("alerts panel lists shortages, near-expiry and cold-chain holds", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /shortages/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /near expiry/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /cold-chain holds/i })).toBeVisible();
});
