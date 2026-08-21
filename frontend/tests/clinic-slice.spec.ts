import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";

/*
 * Controlled inputs can be reset once by React hydration; refill until the
 * values stick, then submit.
 */
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
  throw new Error(`Input "${label}" did not hold value "${value}" (hydration race)`);
}

async function login(page: Page, username = "demo", password = DEMO_PASSWORD) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) {
    await steadyFill(page, "Organisation ID", organisationId);
  }
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("completes the clinic vertical slice across routed workspaces", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { name: /Good (morning|afternoon|evening)/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Today's Queue" })).toBeVisible();

  // Register and check in a patient (reception workspace).
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/\/patients$/);
  const suffix = Date.now().toString().slice(-6);
  const patientName = `Slice Patient${suffix}`;
  await steadyFill(page, "First name", "Slice");
  await steadyFill(page, "Last name", `Patient${suffix}`);
  await steadyFill(page, "Phone", "0700" + suffix);
  await page.locator("form").getByRole("button", { name: "Register patient" }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible();

  await page.getByRole("button", { name: "Check in patient" }).click();
  await expect(page.getByText(new RegExp("checked in as \\w+-\\d{3}"))).toBeVisible();

  // Claim the queue entry (queue workspace).
  await page.locator('nav a[href="/queue"]').click();
  await expect(page).toHaveURL(/\/queue$/);
  await page.getByLabel("Filter queue").fill(patientName);
  const queueRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(queueRow).toBeVisible();
  await queueRow.getByRole("button", { name: "Claim" }).click();
  await expect(queueRow.getByText("Called")).toBeVisible();
  await queueRow.getByRole("button", { name: "Open" }).click();

  // Triage the patient (nurse workspace — admin holds every capability).
  await expect(page).toHaveURL(/\/triage/);
  await expect(page.getByText(patientName).first()).toBeVisible();
  await steadyFill(page, "Chief complaint", "Slice headache");
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText("Triage recorded for " + patientName)).toBeVisible();

  // Consultation (clinician workspace): start, note, two-step sign.
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const consultRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(consultRow).toBeVisible();
  await consultRow.click();

  for (const section of ["Summary", "History", "Examination", "Investigations", "Diagnosis", "Treatment", "Notes"]) {
    await expect(page.getByRole("tab", { name: section, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("tab", { name: "Summary", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Not recorded yet");
  await page.getByRole("tab", { name: "Summary", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Notes", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: "Summary", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Notes", exact: true }).click();

  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByText(/ENC-/)).toBeVisible();
  await page.getByLabel("Consultation note").fill("Assessment: stable. Plan: hydration.");
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Not recorded yet");
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.getByLabel("Consultation note")).toHaveValue("Assessment: stable. Plan: hydration.");
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();

  // A signed note must be read back from the encounter response after a reload.
  await page.reload();
  await expect(page).toHaveURL(/\/consultations$/);
  const reloadedConsultRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(reloadedConsultRow).toBeVisible();
  await reloadedConsultRow.click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
  await expect(page.getByRole("tabpanel")).toContainText("Assessment: stable. Plan: hydration.");

  // Invoice and payment (billing workspace) via the clinician handoff.
  await page.getByRole("button", { name: "Create invoice" }).click();
  await expect(page).toHaveURL(/\/billing\?/);
  await page.getByRole("button", { name: "Create invoice" }).click();
  await expect(page.getByText(new RegExp("Invoice INV-\\S+ created for " + patientName))).toBeVisible();
  await page.getByRole("button", { name: "Post payment" }).click();
  await expect(page.getByText("Payment recorded. Receipt RCT-")).toBeVisible();
  await expect(page.getByText(/^RCT-/).first()).toBeVisible();
});
