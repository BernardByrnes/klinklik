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

test("S-08 shows the exact blocked-closure checklist without changing the Visit", async ({
  page,
}) => {
  await login(page);
  const sessionResponse = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  const headers = {
    Authorization: `Bearer ${session.access_token}`,
    "X-Facility-Id": session.facilities[0].id,
    "Content-Type": "application/json",
  };
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers,
    data: {
      first_name: "S08",
      last_name: `Blocked${suffix}`,
      sex: "FEMALE",
      phone: `076${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers, "Idempotency-Key": `s08-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    invoice_id: string | null;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByText("Visit closure", { exact: true })).toBeVisible();
  const blocked = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/reception/visits/${checkedIn.visit_id}/close/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Close visit", exact: true }).click();
  expect((await blocked).status()).toBe(409);
  await expect(page.getByText("ACTIVE_QUEUE_STAGE", { exact: false })).toBeVisible();
  await expect(page.getByText(/OUTSTANDING_BALANCE/)).toBeVisible();
  await expect(page.getByText("Visit CLOSED")).toHaveCount(0);
});
