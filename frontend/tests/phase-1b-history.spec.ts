import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";
const SYNTHETIC_COMPLAINT = "Phase 1B verification — synthetic presenting complaint";
const SYNTHETIC_HPI = "Phase 1B verification — synthetic HPI\nSecond synthetic line.";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt++) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) {
      await page.waitForTimeout(150);
      if ((await locator.inputValue()) === value) return;
    } else {
      await page.waitForTimeout(300);
    }
  }
  throw new Error("Input did not hold its value: " + label);
}

async function login(page: Page) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) {
    await steadyFill(page, "Organisation ID", organisationId);
  }
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);
}

async function registerAndCheckIn(page: Page, firstName: string, lastName: string, phone: string) {
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/\/patients$/);
  await steadyFill(page, "First name", firstName);
  await steadyFill(page, "Last name", lastName);
  await steadyFill(page, "Phone", phone);
  await page.locator("form").getByRole("button", { name: "Register patient" }).click();
  const patientName = firstName + " " + lastName;
  await expect(page.getByText(new RegExp(patientName + " registered as P-"))).toBeVisible();
  await page.getByRole("button", { name: "Check in patient" }).click();
  await expect(page.getByText(new RegExp(patientName + " checked in as"))).toBeVisible();
  return patientName;
}

async function triageFromQueue(page: Page, patientName: string) {
  await page.locator('nav a[href="/queue"]').click();
  await expect(page).toHaveURL(/\/queue$/);
  await page.getByLabel("Filter queue").fill(patientName);
  const row = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Claim" }).click();
  await expect(row.getByText("Called")).toBeVisible();
  await row.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/triage/);
  await expect(page.getByText(patientName).first()).toBeVisible();
  await steadyFill(page, "Chief complaint", "Phase 1B verification — synthetic triage");
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText(new RegExp("Triage recorded for " + patientName))).toBeVisible();
}

test("persists History fields, isolates patient drafts, and hydrates after reload", async ({ page }) => {
  await login(page);
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/")) failedRequests.push(request.url());
  });

  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1B-A-" + suffix, "Synthetic", "0720" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1B-B-" + suffix, "Synthetic", "0721" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const firstRow = page.getByRole("listitem").filter({ hasText: patientA });
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();

  await steadyFill(page, "Presenting complaint", SYNTHETIC_COMPLAINT);
  await steadyFill(page, "History of present illness (HPI)", SYNTHETIC_HPI);
  const saveResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await saveResponse).status()).toBe(200);
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.getByLabel("Consultation note")).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("Presenting complaint")).toHaveValue(SYNTHETIC_COMPLAINT);
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue(SYNTHETIC_HPI);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await steadyFill(page, "Consultation note", "Phase 1B verification — synthetic Assessment/Plan.");
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();

  const secondRow = page.getByRole("listitem").filter({ hasText: patientB });
  await secondRow.click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
  await expect(page.getByLabel("Presenting complaint")).toHaveCount(0);
  await expect(page.getByText(SYNTHETIC_COMPLAINT)).toHaveCount(0);

  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("Presenting complaint")).toHaveValue("");
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue("");

  await page.reload();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientA }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByText("This History section is signed and immutable.")).toBeVisible();
  await expect(page.getByText(SYNTHETIC_COMPLAINT)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_HPI)).toBeVisible();

  await page.setViewportSize({ width: 768, height: 1024 });
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
