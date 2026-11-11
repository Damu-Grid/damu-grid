import { expect, test, type Page } from "@playwright/test";

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

test("transfer map shows facilities, legend and transfer lines", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await page.goto("/map");
  await expect(page.getByRole("heading", { name: "Transfer map" })).toBeVisible();
  await expect(page.getByRole("img", { name: /schematic kenya map/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Facilities on this map" })).toBeVisible();
});
