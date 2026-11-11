import { expect, test, type Page } from "@playwright/test";

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

test("offline shows banner and saved data", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  // Prime the cache, then cut the API: the app must keep showing saved data.
  await page.route("**/api/backend/**", (route) => route.abort());
  await page.reload();
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await expect(page.getByText(/showing saved data/i)).toBeVisible();
});

test("review action while offline is queued", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await page.route("**/api/backend/**", (route) => route.abort());
  await page.reload();
  await page.getByRole("button", { name: "Accept" }).first().click();
  await page.getByRole("textbox").fill("Offline test: stock confirmed by phone, syncing later.");
  await page.getByRole("button", { name: /accept transfer|submit/i }).click();
  await expect(page.getByText(/queued/i)).toBeVisible();
});
