import { expect, test, type Page } from "@playwright/test";

// Runs against backend/prototype.py on the official synthetic snapshot.
// Uses whatever card the prototype computes; nothing is hard-coded.

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

test("real queue: accept → dispatch → receive, held for safety review", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await expect(page.getByText("Not computed: layout placeholder")).toHaveCount(0);

  const card = page.locator("main li").filter({ has: page.getByRole("button", { name: "Accept" }) }).first();
  await expect(card).toContainText("Synthetic closing snapshot");

  await card.getByRole("button", { name: "Accept" }).click();
  await page.getByLabel("Reason (required)").fill("Integration test against the prototype");
  await page.getByRole("button", { name: "Accept and reserve" }).click();
  const decisions = page.getByRole("region", { name: "Decisions this session" });
  await expect(decisions.getByRole("status")).toContainText("Accepted: units reserved");
  const moveLink = decisions.getByRole("link", { name: /^Move / });
  const moveId = ((await moveLink.textContent()) ?? "").replace(/^Move /, "").trim();

  await signInAs(page, /sending officer/i);
  const toDispatch = page.locator("li").filter({ hasText: `Move ${moveId}: state and audit trail` });
  await toDispatch.getByRole("button", { name: "Recheck and dispatch" }).click();
  for (const box of await page.getByRole("dialog").getByRole("checkbox").all()) await box.check();
  await page.getByRole("button", { name: "Confirm dispatch" }).click();
  await expect(toDispatch).toHaveCount(0);

  await signInAs(page, /receiving officer/i);
  const toReceive = page.locator("li").filter({ hasText: `Move ${moveId}: state and audit trail` });
  await toReceive.getByRole("button", { name: "Confirm receipt" }).click();
  await page.getByRole("radio", { name: /Not sure/ }).check();
  await page.getByRole("dialog").getByRole("button", { name: "Confirm receipt" }).click();
  await expect(toReceive).toHaveCount(0);

  await page.goto(`/moves/${moveId}`);
  await expect(page.getByText("Held for safety review", { exact: true })).toBeVisible();
  const trail = page.getByRole("list", { name: "Audit trail" });
  for (const step of ["accept", "dispatch", "receive"]) await expect(trail).toContainText(step);
});

test("evaluation and snapshot come from the prototype", async ({ page }) => {
  await page.goto("/evaluation");
  // Either real numbers or an explicit error; never placeholder figures.
  await expect(
    page.getByText(/The candidate (did not )?beat the baseline|Could not load the evaluation|Not computed yet/),
  ).toBeVisible();
  await expect(page.getByText(/Live queue built from stock as of/)).toBeVisible();
});
