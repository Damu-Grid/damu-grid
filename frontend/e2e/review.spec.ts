import { expect, test, type Page } from "@playwright/test";

const MOCK_API = "http://localhost:8765";

async function signInAs(page: Page, role: RegExp) {
  await page.goto("/login");
  await page.getByRole("button", { name: role }).click();
}

function cardFor(page: Page, suggestionId: string) {
  return page.locator("li").filter({ hasText: `Mock reason for ${suggestionId}.` });
}

test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK_API}/__reset`);
});

test("coordinator accepts a suggestion with a reason, using the keyboard", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();

  const card = cardFor(page, "MOCK-1");
  await card.getByRole("button", { name: "Accept" }).focus();
  await page.keyboard.press("Enter");

  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Accept this transfer" })).toBeVisible();
  const submit = dialog.getByRole("button", { name: "Accept and reserve" });
  await expect(submit).toBeDisabled(); // reason is required

  await page.keyboard.type("Recipient confirmed it can receive today");
  await page.keyboard.press("Control+Enter");

  await expect(dialog).toBeHidden();
  // The reserved suggestion leaves the queue; the outcome stays visible.
  const decisions = page.getByRole("region", { name: "Decisions this session" });
  await expect(decisions.getByRole("status")).toContainText("Accepted: units reserved");
  await expect(decisions.getByRole("status")).toContainText("Move MOVE-MOCK-1");
  await expect(card).toHaveCount(0);
});

test("a conflicting accept shows a 409 message and does not reserve", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  const card = cardFor(page, "MOCK-CONFLICT");
  await card.getByRole("button", { name: "Accept" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason (required)").fill("Trying to accept");
  await dialog.getByRole("button", { name: "Accept and reserve" }).click();

  await expect(dialog.getByRole("alert")).toContainText("Conflict: this suggestion changed");
  await expect(dialog.getByRole("alert")).toContainText("unit version is stale");
});

test("reject needs a reason from the list", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  const card = cardFor(page, "MOCK-1");
  await card.getByRole("button", { name: "Reject" }).click();

  const dialog = page.getByRole("dialog");
  const submit = dialog.getByRole("button", { name: "Reject" });
  await expect(submit).toBeDisabled();

  await dialog.getByRole("combobox").click();
  await page.getByRole("option", { name: "Receiving hospital refused" }).click();
  await submit.click();

  await expect(page.getByRole("region", { name: "Decisions this session" }).getByRole("status")).toContainText("Rejected: reason recorded");
});

test("change requires a real difference, then submits", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  const card = cardFor(page, "MOCK-1");
  await card.getByRole("button", { name: "Change" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason (required)").fill("Closer hospital has the same gap");
  const submit = dialog.getByRole("button", { name: "Submit change" });
  await expect(submit).toBeDisabled();

  await dialog.getByLabel("Destination facility ID").fill("MOCK-SITE-C");
  await submit.click();
  await expect(page.getByRole("region", { name: "Decisions this session" }).getByRole("status")).toContainText("Changed: a revised suggestion");
});

test("model off shows fallback-rule cards", async ({ page }) => {
  await signInAs(page, /regional stock coordinator/i);
  await page.getByLabel("Model off (fallback rule)").click();
  await expect(page.getByText("Mock fallback rule.")).toBeVisible();
  await expect(page.getByText("Fallback rule · model off")).toBeVisible();
});

test("other roles cannot decide", async ({ page }) => {
  await signInAs(page, /sending officer/i);
  await page.goto("/queue");
  const card = cardFor(page, "MOCK-1");
  await expect(card.getByRole("button", { name: "Accept" })).toBeDisabled();
  await expect(card).toContainText("Only the regional stock coordinator");
});

test("unreachable API shows the not-computed banner", async ({ page }) => {
  await page.route(`${MOCK_API}/suggestions*`, (route) => route.abort());
  await signInAs(page, /regional stock coordinator/i);
  await expect(page.getByText("Not computed: layout placeholder")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accept" }).first()).toBeDisabled();
});
