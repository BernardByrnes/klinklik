import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(200);
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

function headers(session: { token: string; facilityId: string }) {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Facility-Id": session.facilityId,
    "Content-Type": "application/json",
  };
}

test("S-16 low-bandwidth reception journey completes under throttling", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const client = await page.context().newCDPSession(page);
  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 450,
    downloadThroughput: 50 * 1024,
    uploadThroughput: 20 * 1024,
    connectionType: "cellular3g",
  });
  try {
    await page.goto("/patients");
    await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible({
      timeout: 30_000,
    });
    await steadyFill(page, "First name", "S16");
    await steadyFill(page, "Last name", `LowBandwidth${suffix}`);
    await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);
    const form = page
      .locator("form")
      .filter({ has: page.getByLabel("First name", { exact: true }) });
    const registered = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/reception/patients/register/") &&
        response.request().method() === "POST",
      { timeout: 30_000 }
    );
    await form.getByRole("button", { name: "Register patient", exact: true }).click();
    const registration = await registered;
    expect(registration.status()).toBe(201);
    const patientId = ((await registration.json()) as { patient_id: string }).patient_id;
    await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({
      timeout: 30_000,
    });
    // The UI session may rotate the API token; re-login before the API command.
    const refreshed = await apiLogin(page);
    const checkIn = await page.request.post(
      `${API}/api/v1/reception/visits/check-in/`,
      {
        headers: { ...headers(refreshed), "Idempotency-Key": `s16-lowbw-${suffix}` },
        data: {
          patient_id: patientId,
          visit_type: "OUTPATIENT_NEW",
          payer_type: "CASH",
        },
      }
    );
    expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  } finally {
    await client.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 0,
      downloadThroughput: -1,
      uploadThroughput: -1,
      connectionType: "none",
    });
    await client.detach();
  }
});

test("S-16 receipt print renders through the real browser print path", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S16",
      last_name: `Print${suffix}`,
      sex: "FEMALE",
      phone: `074${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok(), await patient.text()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s16-print-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    invoice_id: string;
  };

  const current = await page.request.get(`${API}/api/v1/billing/shifts/current/`, {
    headers: headers(session),
  });
  const openShift = ((await current.json()) as { shift: { id: string } | null }).shift;
  if (openShift) {
    const closed = await page.request.post(
      `${API}/api/v1/billing/shifts/${openShift.id}/close/`,
      {
        headers: {
          ...headers(session),
          "Idempotency-Key": `s16-print-close-${suffix}`,
        },
        data: { declared_cash: "0.00", reason: "Synthetic S-16 print setup cleanup" },
      }
    );
    expect(closed.ok(), await closed.text()).toBeTruthy();
  }

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByRole("heading", { name: "Billing & Payments" })).toBeVisible();
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
  await expect(page.locator("[data-print-sheet]")).toContainText("30000.00");
  const reprinted = page.waitForResponse(
    (response) =>
      /\/api\/v1\/billing\/receipts\/[0-9a-f-]+\/reprint\/$/.test(response.url()) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Print receipt", exact: true }).click();
  expect((await reprinted).status()).toBe(200);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("[data-print-sheet]")).toBeVisible();
  const pdf = await page.pdf({ format: "A4", printBackground: true });
  expect(pdf.byteLength).toBeGreaterThan(1000);
  const digest = createHash("sha256").update(pdf).digest("hex");
  console.log(`S16_PRINT_PDF_BYTES=${pdf.byteLength} SHA256=${digest}`);
});
