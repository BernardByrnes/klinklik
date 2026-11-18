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

test("S-06 issues a credit note, keeps refunds fenced and prints the Z-report", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: "S06",
      last_name: `Correction${suffix}`,
      sex: "FEMALE",
      phone: `079${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `s06-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    invoice_id: string | null;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  const current = await page.request.get(`${API}/api/v1/billing/shifts/current/`, {
    headers: apiHeaders(session),
  });
  const openShift = ((await current.json()) as { shift: { id: string } | null }).shift;
  if (openShift) {
    await page.request.post(
      `${API}/api/v1/billing/shifts/${openShift.id}/close/`,
      {
        headers: { ...apiHeaders(session), "Idempotency-Key": `s06-cleanup-${suffix}` },
        data: { declared_cash: "0.00", reason: "Synthetic E2E setup cleanup" },
      }
    );
  }

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByText("Cashier shift", { exact: true })).toBeVisible();
  const shiftOpened = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/billing/shifts/open/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Open shift", exact: true }).click();
  expect((await shiftOpened).status()).toBe(201);

  await steadyFill(page, "Amount (UGX)", "30000.00");
  const paid = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/billing/invoices/${checkedIn.invoice_id}/payments/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Post payment", exact: true }).click();
  expect((await paid).status()).toBe(201);
  await expect(page.getByText(/Payment recorded\. Receipt RCT-/)).toBeVisible();

  await steadyFill(page, "Credit amount (UGX)", "5000.00");
  await steadyFill(page, "Credit reason", "Synthetic not-rendered service");
  const credit = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/billing/invoices/${checkedIn.invoice_id}/credit-notes/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Issue credit note", exact: true }).click();
  expect((await credit).status()).toBe(201);
  await expect(page.getByText(/Credit note CN-/)).toBeVisible();
  await expect(page.getByText("Refundable credit", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Request refund — MFA required/ })
  ).toBeDisabled();

  const report = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/billing/shifts/") &&
      response.url().endsWith("/z-report/") &&
      response.request().method() === "GET"
  );
  await page.getByRole("button", { name: "Load Z-report", exact: true }).click();
  expect((await report).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Shift Z-report" })).toBeVisible();
  await expect(page.locator("[data-z-report]")).toContainText("CASH");
  await expect(page.locator("[data-z-report]")).toContainText("30000.00");
  await expect(page.getByRole("button", { name: "Print Z-report", exact: true })).toBeVisible();
});
