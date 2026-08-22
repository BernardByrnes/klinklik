import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";
const SYNTHETIC_COMPLAINT = "Phase 1C verification — synthetic presenting complaint";
const SYNTHETIC_HPI = "Phase 1C verification — synthetic HPI";
const SYNTHETIC_PMH = "Phase 1C verification — synthetic past medical history";
const UPDATED_PMH = "Phase 1C verification — updated synthetic past medical history";
const SYNTHETIC_PSH = "Phase 1C verification — synthetic past surgical history";
const SYNTHETIC_NOTE = "Phase 1C verification — synthetic Assessment/Plan.";

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

async function registerAndCheckIn(page: Page, firstName: string, phone: string) {
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/\/patients$/);
  await steadyFill(page, "First name", firstName);
  await steadyFill(page, "Last name", "Synthetic");
  await steadyFill(page, "Phone", phone);
  await page.locator("form").getByRole("button", { name: "Register patient" }).click();
  const patientName = firstName + " Synthetic";
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
  await steadyFill(page, "Chief complaint", "Phase 1C verification — synthetic triage");
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText(new RegExp("Triage recorded for " + patientName))).toBeVisible();
}

async function startHistory(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const row = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(row).toBeVisible();
  await row.click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
}

test("persists and isolates relevant past medical and surgical history", async ({ page }) => {
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
  const patientA = await registerAndCheckIn(page, "Phase1C-A-" + suffix, "0730" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1C-B-" + suffix, "0731" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  await startHistory(page, patientA);
  await steadyFill(page, "Presenting complaint", SYNTHETIC_COMPLAINT);
  await steadyFill(page, "History of present illness (HPI)", SYNTHETIC_HPI);
  await steadyFill(page, "Relevant Past Medical History", SYNTHETIC_PMH);
  await steadyFill(page, "Relevant Past Surgical History", SYNTHETIC_PSH);

  const firstSave = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await firstSave).status()).toBe(200);
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Relevant Past Medical History", UPDATED_PMH);
  const secondSave = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await secondSave).status()).toBe(200);
  await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue(SYNTHETIC_COMPLAINT);
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue(SYNTHETIC_HPI);
  await expect(page.getByLabel("Relevant Past Surgical History")).toHaveValue(SYNTHETIC_PSH);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await steadyFill(page, "Consultation note", SYNTHETIC_NOTE);
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByText("This History section is signed and immutable.")).toBeVisible();
  await expect(page.getByText(SYNTHETIC_COMPLAINT)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_HPI)).toBeVisible();
  await expect(page.getByText(UPDATED_PMH)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_PSH)).toBeVisible();

  const secondRow = page.getByRole("listitem").filter({ hasText: patientB });
  await secondRow.click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
  await expect(page.getByText(SYNTHETIC_PMH)).toHaveCount(0);
  await expect(page.getByText(SYNTHETIC_PSH)).toHaveCount(0);

  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue("");
  await expect(page.getByLabel("Relevant Past Medical History")).toHaveValue("");
  await expect(page.getByLabel("Relevant Past Surgical History")).toHaveValue("");

  await page.reload();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientA }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByText("This History section is signed and immutable.")).toBeVisible();
  await expect(page.getByText(SYNTHETIC_COMPLAINT)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_HPI)).toBeVisible();
  await expect(page.getByText(UPDATED_PMH)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_PSH)).toBeVisible();
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.getByText(SYNTHETIC_NOTE)).toBeVisible();

  await page.setViewportSize({ width: 768, height: 1024 });
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
