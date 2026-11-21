import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) {
      await page.waitForTimeout(150);
      if ((await locator.inputValue()) === value) return;
    }
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
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/overview$/);
}

async function apiLogin(page: Page) {
  const response = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  return { token: body.access_token, facilityId: body.facilities[0].id };
}

function apiHeaders(session: { token: string; facilityId: string }) {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Facility-Id": session.facilityId,
    "Content-Type": "application/json",
  };
}

test("S-05 cashier opens a shift, collects exactly, reprints and reverses before a blind close", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: "S05",
      last_name: `Cashier${suffix}`,
      sex: "FEMALE",
      phone: `078${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `s05-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    invoice_id: string | null;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  // A previous interrupted run may have left this synthetic cashier's shift
  // open; close it through the same command before starting the journey.
  const current = await page.request.get(`${API}/api/v1/billing/shifts/current/`, {
    headers: apiHeaders(session),
  });
  const openShift = ((await current.json()) as { shift: { id: string } | null }).shift;
  if (openShift) {
    const closed = await page.request.post(
      `${API}/api/v1/billing/shifts/${openShift.id}/close/`,
      {
        headers: {
          ...apiHeaders(session),
          "Idempotency-Key": `s05-cleanup-close-${suffix}`,
        },
        data: { declared_cash: "0.00", reason: "Synthetic E2E setup cleanup" },
      }
    );
    expect(closed.ok(), await closed.text()).toBeTruthy();
  }

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByRole("heading", { name: "Billing & Payments" })).toBeVisible();
  await expect(page.getByText("Cashier shift", { exact: true })).toBeVisible();
  const shiftOpened = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/billing/shifts/open/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Open shift", exact: true }).click();
  expect((await shiftOpened).status()).toBe(201);
  await expect(page.getByText(/Shift open since/)).toBeVisible();
  // The blind boundary is removed from the open drawer: no tender totals are
  // available through this card until a committed close is shown.
  await expect(page.getByRole("button", { name: "Load Z-report", exact: true })).toHaveCount(0);

  // First payment: shift-bound canonical command.
  await steadyFill(page, "Amount (UGX)", "10000.00");
  const firstPayment = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/billing/invoices/${checkedIn.invoice_id}/payments/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Post payment", exact: true }).click();
  expect((await firstPayment).status()).toBe(201);
  await expect(page.getByText(/Payment recorded\. Receipt RCT-/)).toBeVisible();
  await expect(page.locator("[data-print-sheet]")).toContainText("10000.00");

  // Second payment: the receipt must be read by its committed identity.
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByText("This invoice is paid in full.")).toHaveCount(0);
  await steadyFill(page, "Amount (UGX)", "20000.00");
  const receiptByIidentity = page.waitForResponse(
    (response) =>
      /\/api\/v1\/billing\/receipts\/[0-9a-f-]+\/$/.test(response.url()) &&
      response.request().method() === "GET"
  );
  await page.getByRole("button", { name: "Post payment", exact: true }).click();
  expect((await receiptByIidentity).status()).toBe(200);
  await expect(page.locator("[data-print-sheet]")).toContainText("20000.00");
  await expect(page.locator("[data-print-sheet]")).toContainText("0.00");

  // CMD-081 reprint is an audited, idempotent intent over the same receipt.
  const reprinted = page.waitForResponse(
    (response) =>
      /\/api\/v1\/billing\/receipts\/[0-9a-f-]+\/reprint\/$/.test(response.url()) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Print receipt", exact: true }).click();
  expect((await reprinted).status()).toBe(200);

  // Whole-payment reversal restores the balance without deleting evidence.
  await page.getByRole("button", { name: "Reverse whole payment", exact: true }).first().click();
  await steadyFill(page, "Reversal reason", "Synthetic wrong tender");
  const reversed = page.waitForResponse(
    (response) =>
      /\/api\/v1\/billing\/payments\/[0-9a-f-]+\/reverse\/$/.test(response.url()) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Confirm reversal", exact: true }).click();
  expect((await reversed).status()).toBe(200);
  await expect(page.getByText(/Payment reversed\./)).toBeVisible();
  await expect(page.getByText("CASH · REVERSED")).toBeVisible();

  // Blind close: the declaration is reviewed before the expected cash appears.
  await steadyFill(page, "Declared cash", "9000.00");
  await page.getByRole("button", { name: "Review close", exact: true }).click();
  const confirmation = page.locator("[data-confirm-close]");
  await expect(confirmation).toContainText("9000.00");
  await expect(confirmation).not.toContainText("Expected 20000.00");
  const closed = page.waitForResponse(
    (response) =>
      response.url().endsWith("/close/") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Confirm close", exact: true }).click();
  expect((await closed).status()).toBe(200);
  await expect(page.getByText(/Expected 20000\.00/)).toBeVisible();
  await expect(page.getByText(/variance -11000\.00/).first()).toBeVisible();

  // The committed close is a distinct previous-shift summary and survives reload.
  const previous = page.locator("[data-last-closed-shift]");
  await expect(previous).toContainText("Previous shift (closed)");
  await expect(previous).toContainText("20000.00");
  await page.reload();
  await expect(page).toHaveURL(/\/billing\?visit=/);
  const reloaded = page.locator("[data-last-closed-shift]");
  await expect(reloaded).toContainText("Previous shift (closed)");
  await expect(reloaded).toContainText("20000.00");
  await expect(page.getByRole("button", { name: "Open shift", exact: true })).toBeVisible();

  // A Z-report is available only from the committed closed summary.
  await page.getByRole("button", { name: "Load Z-report", exact: true }).click();
  await expect(page.locator("[data-z-report]")).toContainText("Shift Z-report");
  await expect(page.locator("[data-z-report]")).toContainText("20000.00");
});
