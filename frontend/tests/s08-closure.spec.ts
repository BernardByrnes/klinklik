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

async function createVisitedInvoice(page: Page) {
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
  expect(patient.ok(), await patient.text()).toBeTruthy();
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
  return checkedIn as { visit_id: string; invoice_id: string };
}

function readinessBody(visitId: string, overrides: Record<string, unknown> = {}) {
  return {
    visit_id: visitId,
    state: "OPEN",
    version: 7,
    closure_reason: "",
    ready: false,
    blockers: [
      { code: "ACTIVE_QUEUE_STAGE", queue_type: "CONSULTATION", state: "WAITING" },
      {
        code: "OUTSTANDING_BALANCE",
        invoice_no: "INV-S08",
        amount: "30000.00",
      },
    ],
    ...overrides,
  };
}

test("S-08/S-39 readiness lists blockers before any close POST", async ({ page }) => {
  await login(page);
  const checkedIn = await createVisitedInvoice(page);
  const closePosts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith(`/api/v1/reception/visits/${checkedIn.visit_id}/close/`)
    ) {
      closePosts.push(request.url());
    }
  });

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByText("Visit closure", { exact: true })).toBeVisible();
  await expect(page.getByText("Active queue stage")).toBeVisible();
  await expect(page.getByText(/Outstanding balance/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Close visit", exact: true })).toBeDisabled();
  await expect(page.getByText("Visit CLOSED")).toHaveCount(0);
  expect(closePosts).toHaveLength(0);
});

for (const [label, overrides, expected] of [
  ["clear", { ready: true, blockers: [] }, "All known closure blockers are clear"],
  ["closed", { state: "CLOSED", ready: false, blockers: [] }, "Visit CLOSED"],
  ["unknown", { state: "UNKNOWN_STATE", ready: true, blockers: [] }, "closure state could not be confirmed"],
] as const) {
  test(`S-39 readiness shows the ${label} state`, async ({ page }) => {
    await login(page);
    const checkedIn = await createVisitedInvoice(page);
    await page.route("**/closure-readiness/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(readinessBody(checkedIn.visit_id, overrides)),
      });
    });
    await page.goto(`/billing?visit=${checkedIn.visit_id}`);
    await expect(page.getByText(expected, { exact: false })).toBeVisible();
    if (label === "clear") {
      await expect(page.getByRole("button", { name: "Close visit", exact: true })).toBeEnabled();
    } else {
      await expect(page.getByRole("button", { name: "Close visit", exact: true })).toHaveCount(0);
    }
  });
}

test("S-39 readiness unavailable keeps the form safe", async ({ page }) => {
  await login(page);
  const checkedIn = await createVisitedInvoice(page);
  await page.route("**/closure-readiness/", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ code: "MIGRATION_TARGET_DISABLED", detail: "Unavailable" }),
    });
  });
  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByText(/checklist could not be loaded/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Close visit", exact: true })).toHaveCount(0);
});

test("S-39 dropped close response retries the same key and shows confirmed closure", async ({
  page,
}) => {
  await login(page);
  const checkedIn = await createVisitedInvoice(page);
  await page.route("**/closure-readiness/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(readinessBody(checkedIn.visit_id, { ready: true, blockers: [] })),
    });
  });
  const keys: string[] = [];
  let attempt = 0;
  await page.route(`**/api/v1/reception/visits/${checkedIn.visit_id}/close/`, async (route) => {
    keys.push(route.request().headers()["idempotency-key"] ?? "");
    attempt += 1;
    if (attempt === 1) {
      await route.abort("failed");
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        visit_id: checkedIn.visit_id,
        state: "CLOSED",
        closure_reason: "COMPLETED",
        version: 8,
        closed: true,
        already_closed: false,
        blockers: [],
      }),
    });
  });

  await page.goto(`/billing?visit=${checkedIn.visit_id}`);
  await expect(page.getByRole("button", { name: "Close visit", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Close visit", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("pending-intent-review").click();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText(/Visit closed \(COMPLETED\)/)).toBeVisible({ timeout: 15_000 });
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
  expect(keys[0]).toBeTruthy();
});
