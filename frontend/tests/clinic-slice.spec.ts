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

async function setNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await statusResponse;
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
}

async function saveTreatedDisposition(page: Page) {
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/disposition/") && response.status() === 200,
  );
  await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  await responsePromise;
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
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

  // Observe the canonical check-in before clicking so the handoff is asserted
  // against the invoice that check-in actually issued.
  const checkInResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/reception/visits/check-in/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Check in patient" }).click();
  const checkInResponse = await checkInResponsePromise;
  expect(checkInResponse.ok()).toBeTruthy();
  const checkInBody = (await checkInResponse.json()) as {
    visit_id: string;
    invoice_id: string | null;
  };
  expect(checkInBody.invoice_id).toBeTruthy();
  const visitId = checkInBody.visit_id;
  const invoiceId = checkInBody.invoice_id as string;
  await expect(page.getByRole("status").filter({ hasText: "checked in." })).toContainText(
    patientName + " checked in.",
  );

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
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", "Phase 1N-B compatibility synthetic no final diagnosis");
  await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
  await expect(page.getByTestId("no-diagnosis-state")).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", "Phase 1L-A browser compatibility synthetic complaint");
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByLabel("Consultation note").fill("Assessment: stable. Plan: hydration.");
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("General Examination");
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.getByLabel("Consultation note")).toHaveValue("Assessment: stable. Plan: hydration.");
  await setNkaAndReview(page);
  await saveTreatedDisposition(page);
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

  // The signed consultation opens the invoice check-in already issued.
  const invoiceCreateRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "POST") return;
    const pathname = new URL(request.url()).pathname;
    if (pathname === "/api/v1/billing/invoices/") invoiceCreateRequests.push(request.url());
  });
  const visitInvoicePromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/v1/billing/invoices/by-visit/${visitId}/`) &&
      response.request().method() === "GET" &&
      response.status() === 200,
  );
  await page.getByRole("link", { name: "Open invoice" }).click();
  await expect(page).toHaveURL(new RegExp(`/billing\\?visit=${visitId}`));
  const visitInvoiceResponse = await visitInvoicePromise;
  const visitInvoiceBody = (await visitInvoiceResponse.json()) as {
    id: string;
    invoice_no: string;
    visit: string;
  };
  expect(visitInvoiceBody.id).toBe(invoiceId);
  expect(visitInvoiceBody.visit).toBe(visitId);
  const invoiceNumber = visitInvoiceBody.invoice_no;

  // Focused mode is the only invoice in play: no new-invoice form or action.
  await expect(page.getByRole("heading", { name: "New invoice" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create invoice" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Visit invoice" })).toBeVisible();

  const payResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/billing/invoices/${invoiceId}/pay/`) &&
      response.request().method() === "POST",
  );
  const receiptResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/billing/invoices/${invoiceId}/receipt/`) &&
      response.request().method() === "GET",
  );
  await page.getByRole("button", { name: "Post payment" }).click();
  const payResponse = await payResponsePromise;
  expect(payResponse.ok()).toBeTruthy();
  expect(payResponse.url()).toContain(invoiceId);
  const receiptResponse = await receiptResponsePromise;
  expect(receiptResponse.ok()).toBeTruthy();
  expect(receiptResponse.url()).toContain(invoiceId);

  await expect(page.getByText("Payment recorded. Receipt RCT-")).toBeVisible();
  const printedReceipt = page.locator("[data-print-sheet]");
  await expect(printedReceipt).toContainText("Receipt");
  await expect(printedReceipt).toContainText(invoiceNumber);
  await expect(printedReceipt).toContainText(patientName);

  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByText("This invoice is paid in full.")).toBeVisible();

  // No generic invoice-create request was made anywhere in the focused flow.
  expect(invoiceCreateRequests).toEqual([]);
});
