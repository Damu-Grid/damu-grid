import { expect, test, type Page } from "@playwright/test";

const MOCK_API = "http://localhost:8765";

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

function moveRow(page: Page, moveId: string) {
  return page.locator("li").filter({ hasText: `Move ${moveId}: state and audit trail` });
}

test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK_API}/__reset`);
});

test("accept → dispatch → receive, with the audit trail", async ({ page }) => {
  // Coordinator accepts.
  await signInAs(page, /regional stock coordinator/i);
  const card = page.locator("li").filter({ hasText: "Mock reason for MOCK-1." });
  await card.getByRole("button", { name: "Accept" }).click();
  await page.getByLabel("Reason (required)").fill("Recipient can receive today");
  await page.getByRole("button", { name: "Accept and reserve" }).click();
  await expect(page.getByRole("link", { name: "Move MOVE-MOCK-1" })).toBeVisible();

  // Sender rechecks and dispatches.
  await signInAs(page, /sending officer/i);
  await expect(page.getByRole("heading", { name: "Dispatch" })).toBeVisible();
  const toDispatch = moveRow(page, "MOVE-MOCK-1");
  await expect(toDispatch).toContainText("Lease:");
  await toDispatch.getByRole("button", { name: "Recheck and dispatch" }).click();
  const dialog = page.getByRole("dialog");
  const confirm = dialog.getByRole("button", { name: "Confirm dispatch" });
  await expect(confirm).toBeDisabled();
  for (const box of await dialog.getByRole("checkbox").all()) await box.check();
  await confirm.click();
  await expect(toDispatch).toHaveCount(0);

  // Receiver confirms with good cold-chain evidence.
  await signInAs(page, /receiving officer/i);
  await expect(page.getByText("Receipt is not a release for transfusion.")).toBeVisible();
  const toReceive = moveRow(page, "MOVE-MOCK-1");
  await toReceive.getByRole("button", { name: "Confirm receipt" }).click();
  await page.getByRole("radio", { name: /Cool box stayed in range/ }).check();
  await page.getByLabel(/maximum temperature/).fill("5.5");
  await page.getByRole("dialog").getByRole("button", { name: "Confirm receipt" }).click();
  await expect(toReceive).toHaveCount(0);

  // Audit trail shows every step.
  await page.goto("/moves/MOVE-MOCK-1");
  await expect(page.getByText("Received", { exact: true })).toBeVisible();
  const trail = page.getByRole("list", { name: "Audit trail" });
  await expect(trail).toContainText("accept");
  await expect(trail).toContainText("dispatch");
  await expect(trail).toContainText("receive");
});

test("an expired lease cannot be dispatched", async ({ page }) => {
  await signInAs(page, /sending officer/i);
  const row = moveRow(page, "MOVE-SEED-EXPIRED");
  await expect(row.getByRole("button", { name: "Recheck and dispatch" })).toBeDisabled();
  await expect(row).toContainText("Reservation lease expired");
});

test("receipt without cold-chain evidence is held for the safety officer", async ({ page }) => {
  await signInAs(page, /receiving officer/i);
  const row = moveRow(page, "MOVE-SEED-TRANSIT");
  await row.getByRole("button", { name: "Confirm receipt" }).click();
  const confirm = page.getByRole("dialog").getByRole("button", { name: "Confirm receipt" });
  await expect(confirm).toBeDisabled(); // evidence must be stated
  await page.getByRole("radio", { name: /Not sure/ }).check();
  await confirm.click();

  await page.goto("/moves/MOVE-SEED-TRANSIT");
  await expect(page.getByText("Held for safety review", { exact: true })).toBeVisible();
  await expect(page.getByText("Received, held for safety review", { exact: true })).toBeVisible();
  await expect(page.getByText("Only the safety officer can clear")).toBeVisible();
});

test("only the sender can dispatch", async ({ page }) => {
  await signInAs(page, /receiving officer/i);
  await page.goto("/dispatch");
  const row = moveRow(page, "MOVE-SEED-EXPIRED");
  await expect(row.getByRole("button", { name: "Recheck and dispatch" })).toBeDisabled();
  await expect(row).toContainText("Only the sending officer");
});
