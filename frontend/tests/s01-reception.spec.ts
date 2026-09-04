import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt++) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(250);
  }
  throw new Error(`Input "${label}" did not hold its value`);
}

async function login(page: Page) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("S-01 reception supports enquiry conversion, cancellation, and accessible workflow states", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  await expect(page.getByText("No patient selected.", { exact: true })).toBeVisible();

  // REC-013: an operational enquiry is recorded without creating a patient.
  await page.getByLabel("Reason", { exact: true }).selectOption("SERVICE_UNAVAILABLE");
  await steadyFill(page, "Safe notes (optional)", "No clinician available at the desk");
  await page.getByRole("button", { name: "Record enquiry", exact: true }).click();
  await expect(page.getByText("Enquiry recorded and ready to link to the next check-in.", { exact: true })).toBeVisible();

  const suffix = Date.now().toString().slice(-7);
  await steadyFill(page, "First name", "S01");
  await steadyFill(page, "Last name", `Reception${suffix}`);
  await steadyFill(page, "Phone", `0709${suffix}`);
  const registrationForm = page.locator("form").filter({ has: page.getByLabel("First name", { exact: true }) });
  await registrationForm.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible();

  // REC-001: the selected patient exposes labelled visit/payer controls and
  // the enquiry conversion notice before the command is submitted.
  const visitTypes = page.getByRole("radiogroup", { name: "Visit type", exact: true });
  await expect(visitTypes).toBeVisible();
  await expect(visitTypes.getByRole("radio", { name: "Outpatient — new", exact: true })).toBeChecked();
  await expect(page.getByRole("radiogroup", { name: "Payer", exact: true })).toBeVisible();
  await expect(page.getByText("This check-in will convert the recorded arrival enquiry atomically.", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Check in patient", exact: true }).click();
  await expect(page.getByText(/checked in as/)).toBeVisible();
  await expect(page.getByText("Open visit already exists today", { exact: true })).toBeVisible();

  // REC-010: disabled until a reason exists, then leaves a retained context.
  const cancellationReason = page.getByLabel("Cancellation reason", { exact: true });
  const cancelButton = page.getByRole("button", { name: "Cancel erroneous check-in", exact: true });
  await expect(cancellationReason).toBeVisible();
  await expect(cancelButton).toBeDisabled();
  await steadyFill(page, "Cancellation reason", "Wrong patient selected");
  await expect(cancelButton).toBeEnabled();
  await cancelButton.click();
  await expect(page.getByText("Check-in cancelled in error", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "View cancelled visit context", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "View cancelled visit context", exact: true }).click();
  await expect(page.getByText("Visit context", { exact: true })).toBeVisible();
  await expect(page.getByText("CANCELLED_ERROR", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Close visit context", exact: true })).toBeVisible();
});
