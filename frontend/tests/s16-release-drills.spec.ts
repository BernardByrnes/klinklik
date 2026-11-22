import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";

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

const SWITCH_A = "s42a@clinicopus.local";
const SWITCH_B = "s42b@clinicopus.local";
const SWITCH_PASSWORD = "S42Synthetic123!";

function ensureSwitchUsers() {
  const script = `
from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from accounts.services import ensure_default_permissions
from tenancy.models import Department, Facility, Organisation
org = Organisation.objects.get(slug="clinicopus-demo")
facility = Facility.objects.get(organisation=org, code="MAIN")
department = Department.objects.filter(organisation=org, facility=facility).first()
ensure_default_permissions(org)
role = Role.objects.get(organisation=org, template_code="OWNER_ADMIN")
for username in ["${SWITCH_A}", "${SWITCH_B}"]:
    user, _ = User.objects.get_or_create(username=username, defaults={"email": username})
    user.set_password("${SWITCH_PASSWORD}")
    user.save()
    OrganisationMembership.objects.get_or_create(organisation=org, user=user)
    UserFacilityRole.objects.get_or_create(
        organisation=org, user=user, facility=facility,
        defaults={"role": role, "department": department},
    )
`;
  execFileSync("python", ["../backend/manage.py", "shell", "-c", script], {
    cwd: path.resolve(__dirname, ".."),
    encoding: "utf8",
  });
}

async function loginAs(page: Page, username: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/(overview|patients)$/);
}

async function signInHere(page: Page, username: string, password: string) {
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/(overview|patients)$/);
}

async function apiLoginAs(page: Page, username: string, password: string) {
  const response = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username, password },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  return { token: body.access_token, facilityId: body.facilities[0].id };
}

async function startPendingRegistration(page: Page, label: string) {
  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  await steadyFill(page, "First name", "S42");
  await steadyFill(page, "Last name", label);
  await steadyFill(page, "Phone", "0751234567");
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (route.request().method() === "POST") await route.abort("failed");
    else await route.continue();
  });
  const form = page.locator("form").filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });
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

test("S-33 connectivity status is accessible and offline blocks completion", async ({
  page,
}) => {
  await login(page);
  await page.goto("/patients");
  const status = page.getByTestId("connectivity-status");
  await expect(status).toContainText("Online");
  await expect(status).toContainText("Patients");

  const client = await page.context().newCDPSession(page);
  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: true,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
    connectionType: "none",
  });
  try {
    await expect(status).toContainText("Offline", { timeout: 10_000 });
    const register = page
      .getByLabel("Register patient")
      .getByRole("button", { name: "Register patient", exact: true });
    await expect(register).toBeDisabled();
    await expect(status).toContainText("Completion is unavailable");
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

test("S-33 lost registration response recovers with the same key and no duplicate", async ({
  page,
}) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const fullName = `S33 Recovery${suffix}`;
  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  await steadyFill(page, "First name", "S33");
  await steadyFill(page, "Last name", `Recovery${suffix}`);
  await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);

  const attempts: Array<{ key: string; body: string | null }> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/reception/patients/register/")
    ) {
      attempts.push({
        key: request.headers()["idempotency-key"] ?? "",
        body: request.postData(),
      });
    }
  });
  let failures = 0;
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (failures < 2) {
      failures += 1;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  const review = page.getByTestId("pending-intent-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(fullName)).toHaveCount(0);

  const retryButton = page.getByRole("button", { name: "Retry", exact: true });
  if ((await review.getAttribute("aria-expanded")) === "false") await review.click();
  await retryButton.click();
  await expect(review).toBeVisible({ timeout: 15_000 });
  if ((await review.getAttribute("aria-expanded")) === "false") await review.click();
  await expect(retryButton).toHaveCount(1);

  await retryButton.click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({ timeout: 15_000 });
  expect(attempts).toHaveLength(3);
  expect(attempts[1].key).toBe(attempts[0].key);
  expect(attempts[2].key).toBe(attempts[0].key);
  expect(attempts[1].body).toBe(attempts[0].body);
  expect(attempts[2].body).toBe(attempts[0].body);
  expect(attempts[0].key).toBeTruthy();
  await expect(review).toHaveCount(0);
});

test("S-33 authority change clears a pending intent and protected data", async ({
  page,
}) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const fullName = `S33 Authority${suffix}`;
  await page.goto("/patients");
  await steadyFill(page, "First name", "S33");
  await steadyFill(page, "Last name", `Authority${suffix}`);
  await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);

  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    await route.abort("failed");
  });
  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText(fullName)).toHaveCount(0);

  await login(page);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
});

test("S-35 Fix 3 mobile recovery keeps an in-progress command intent", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  await page.goto("/patients");
  await expect(page.getByTestId("connectivity-status")).toBeVisible();
  await steadyFill(page, "First name", "S35");
  await steadyFill(page, "Last name", `InProgress${suffix}`);
  await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);

  const keys: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/reception/patients/register/")
    ) {
      keys.push(request.headers()["idempotency-key"] ?? "");
    }
  });
  let inProgress = false;
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (!inProgress) {
      inProgress = true;
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          code: "IDEMPOTENCY_IN_PROGRESS",
          detail: "The same command is still being completed.",
        }),
      });
      return;
    }
    await route.continue();
  });

  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("pending-intent-review").click();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({ timeout: 15_000 });
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
});

test("S-35 Fix 3 retry waits for reconnect and stays mobile-accessible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  await page.goto("/patients");
  await steadyFill(page, "First name", "S35");
  await steadyFill(page, "Last name", `Offline${suffix}`);
  await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);

  let lost = false;
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (!lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("pending-intent-review").click();

  const client = await page.context().newCDPSession(page);
  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: true,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
    connectionType: "none",
  });
  try {
    await expect(page.getByTestId("connectivity-status")).toContainText("Offline");
    await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeDisabled();
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
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({ timeout: 15_000 });
});

test("S-35 Fix 4 a changed form cannot alter a pending registration", async ({
  page,
}) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  await page.goto("/patients");
  await steadyFill(page, "First name", "S35");
  await steadyFill(page, "Last name", `Snapshot${suffix}`);
  await steadyFill(page, "Phone", `075${suffix.slice(-6).padStart(6, "0")}`);

  const bodies: Array<string | null> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/reception/patients/register/")
    ) {
      bodies.push(request.postData());
    }
  });
  let lost = false;
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (!lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByTestId("pending-intent-review")).toBeVisible({ timeout: 15_000 });
  await steadyFill(page, "Last name", `Changed${suffix}`);

  await page.getByTestId("pending-intent-review").click();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({ timeout: 15_000 });
  expect(bodies).toHaveLength(2);
  expect(bodies[1]).toBe(bodies[0]);
  expect(bodies[0]).toContain(`Snapshot${suffix}`);
  expect(bodies[1]).not.toContain(`Changed${suffix}`);
});

test("S-35 Fix 4 duplicate resolution survives a changed reason on retry", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const phone = `076${suffix.slice(-6).padStart(6, "0")}`;
  const existing = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S35",
      last_name: `Duplicate${suffix}`,
      sex: "FEMALE",
      date_of_birth: "1990-05-14",
      phone,
    },
  });
  expect(existing.ok(), await existing.text()).toBeTruthy();

  await page.goto("/patients");
  await steadyFill(page, "First name", "S35");
  await steadyFill(page, "Last name", `Duplicate${suffix}`);
  await steadyFill(page, "Phone", phone);
  await page.getByLabel("Sex", { exact: true }).selectOption("FEMALE");
  await steadyFill(page, "Date of birth", "1990-05-14");

  const bodies: Array<string | null> = [];
  let attempt = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/reception/patients/register/")
    ) {
      bodies.push(request.postData());
    }
  });
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    attempt += 1;
    if (attempt === 2) {
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("First name", { exact: true }) });
  await form.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByText("Possible duplicate", { exact: true })).toBeVisible({ timeout: 15_000 });
  const reason = page.getByLabel("Reason this is not the same patient", { exact: true });
  await reason.fill(`Original reason ${suffix}`);
  await page.getByRole("button", { name: "Not the same — create new", exact: true }).click();
  const review = page.getByTestId("pending-intent-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  await reason.fill(`Changed reason ${suffix}`);
  if ((await review.getAttribute("aria-expanded")) === "false") await review.click();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible({ timeout: 15_000 });
  expect(bodies).toHaveLength(3);
  expect(bodies[2]).toBe(bodies[1]);
  expect(bodies[1]).toContain(`Original reason ${suffix}`);
  expect(bodies[2]).not.toContain(`Changed reason ${suffix}`);
  await expect(review).toHaveCount(0);
});

test("S-33 throttled worklist records cold and warm samples", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page);
  const client = await page.context().newCDPSession(page);
  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 450,
    downloadThroughput: 50 * 1024,
    uploadThroughput: 20 * 1024,
    connectionType: "cellular3g",
  });
  const samples: number[] = [];
  try {
    let started = Date.now();
    await page.goto("/patients");
    await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible({ timeout: 60_000 });
    samples.push(Date.now() - started);
    await page.getByRole("link", { name: "Overview", exact: true }).click();
    started = Date.now();
    await page.getByRole("link", { name: "Patients", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible({ timeout: 60_000 });
    samples.push(Date.now() - started);
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
  const sorted = [...samples].sort((a, b) => a - b);
  console.log(`S33_NFR_PROFILE=450ms,50KB/s,20KB/s samples=${samples.join(",")} p95=${sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1)]}`);
});

test("S-42 deliberate exit clears the old workspace before the logout response", async ({
  page,
}) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  const suffix = Date.now().toString().slice(-6);
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  await startPendingRegistration(page, `Drop${suffix}`);
  const root = page.locator("[data-authority-epoch]");
  const epochBefore = await root.getAttribute("data-authority-epoch");
  expect(epochBefore).toBeTruthy();

  let logoutStarted = false;
  let releaseLogout: (() => void) | null = null;
  await page.route("**/api/v1/auth/logout/", async (route) => {
    logoutStarted = true;
    await new Promise<void>((resolve) => {
      releaseLogout = resolve;
    });
    await route.abort("failed");
  });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect.poll(() => logoutStarted).toBe(true);
  // The old authority must be invalidated and the subtree unmounted while the
  // network request is still outstanding.
  await expect(root).toHaveCount(0);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
  await expect(page.getByText(/Server sign-out could not be confirmed/)).toHaveCount(0);

  // Ensure the login page is mounted before the late logout failure writes the marker.
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  releaseLogout?.();
  await expect(page).toHaveURL(/\/login$/);
  await expect
    .poll(() => page.evaluate(() => window.localStorage.getItem("klinklik:logout-unconfirmed")))
    .toBe("1");
  // The already-mounted login page must report the late failure without a reload.
  await expect(page.getByText(/Server sign-out could not be confirmed/)).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue("");

  await page.goBack();
  await expect(page).toHaveURL(/\/login$/);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test("S-42 blocked marker storage still clears the former workspace", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("localStorage writes are blocked");
    };
  });
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  await startPendingRegistration(page, `Blocked${Date.now().toString().slice(-6)}`);
  const root = page.locator("[data-authority-epoch]");
  expect(await root.getAttribute("data-authority-epoch")).toBeTruthy();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(root).toHaveCount(0);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue("");
  await page.waitForTimeout(1500);
  await expect(page).toHaveURL(/\/login$/);
  await expect(root).toHaveCount(0);
});

test("S-42 one tab's deliberate exit clears another open tab", async ({ page }) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  const suffix = Date.now().toString().slice(-6);
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  await startPendingRegistration(page, `TwoTab${suffix}`);

  const second = await page.context().newPage();
  // The shared refresh cookie restores A in the second tab before any switch.
  await second.goto("/patients");
  await expect(second.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  await second.getByRole("button", { name: "Account menu" }).click();
  await expect(second.getByRole("menu")).toContainText(SWITCH_A);

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);

  await expect(second).toHaveURL(/\/login$/);
  await expect(second.getByRole("menu")).toHaveCount(0);
  await expect(second.getByTestId("pending-intent-review")).toHaveCount(0);
  await second.close();
});

test("S-42 switch user survives a late logout and requires explicit B sign-in", async ({
  page,
}) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  const suffix = Date.now().toString().slice(-6);
  const aLabel = `SwitchA${suffix}`;
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  await startPendingRegistration(page, aLabel);

  const targetBodies: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/reception/patients/register/")
    ) {
      targetBodies.push(request.postData() ?? "");
    }
  });

  let releaseLogout: (() => void) | null = null;
  await page.route("**/api/v1/auth/logout/", async (route) => {
    await new Promise<void>((resolve) => {
      releaseLogout = resolve;
    });
    await route.abort("failed");
  });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue("");
  await expect(page.getByText(/Server sign-out could not be confirmed/)).toHaveCount(0);

  await steadyFill(page, "Username", SWITCH_B);
  await steadyFill(page, "Password", "wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);

  await signInHere(page, SWITCH_B, SWITCH_PASSWORD);
  const epochB = await page.locator("[data-authority-epoch]").getAttribute("data-authority-epoch");
  expect(epochB).toBeTruthy();

  releaseLogout?.();
  await page.waitForTimeout(1000);
  await expect(page).toHaveURL(/\/(overview|patients)$/);
  expect(await page.locator("[data-authority-epoch]").getAttribute("data-authority-epoch")).toBe(epochB);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
  await expect(page.getByText(aLabel, { exact: false })).toHaveCount(0);
  expect(targetBodies.some((body) => body.includes(aLabel))).toBe(false);

  await page.reload();
  await expect(page).toHaveURL(/\/(overview|patients)$/);
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(page.getByRole("menu")).toContainText(SWITCH_B);
});

test("S-42 confirmed logout revokes the old bearer for protected requests", async ({
  page,
}) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  let bearer = "";
  let facility = "";
  page.on("request", (request) => {
    const authorization = request.headers()["authorization"];
    if (authorization?.startsWith("Bearer ")) {
      bearer = authorization;
      facility = request.headers()["x-facility-id"] ?? "";
    }
  });
  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  expect(bearer).toBeTruthy();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);

  const protectedRequest = await page.request.get(`${API}/api/v1/auth/me/`, {
    headers: {
      Authorization: bearer,
      "X-Facility-Id": facility,
      "Content-Type": "application/json",
    },
  });
  expect(protectedRequest.status()).toBe(401);
  await expect(page).toHaveURL(/\/login$/);
});

test("S-42 blocked marker writes with a still-valid refresh cookie stay locked", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("localStorage writes are blocked");
    };
  });
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);
  const root = page.locator("[data-authority-epoch]");
  expect(await root.getAttribute("data-authority-epoch")).toBeTruthy();

  let releaseLogout: (() => void) | null = null;
  await page.route("**/api/v1/auth/logout/", async (route) => {
    await new Promise<void>((resolve) => {
      releaseLogout = resolve;
    });
    // The server never processes this logout, so A's refresh cookie stays valid.
    await route.abort("failed");
  });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(root).toHaveCount(0);
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  releaseLogout?.();

  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(root).toHaveCount(0);
  await expect(page.getByLabel("Username", { exact: true })).toHaveValue("");
  await page.goto("/patients");
  await expect(page).toHaveURL(/\/login$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/login$/);
  await expect(root).toHaveCount(0);
});

test("S-42 a late logout request cannot delete the new user's cookie", async ({
  page,
}) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);

  let logoutHeld = false;
  let releaseLogout: (() => void) | null = null;
  await page.route("**/api/v1/auth/logout/", async (route) => {
    logoutHeld = true;
    await new Promise<void>((resolve) => {
      releaseLogout = resolve;
    });
    try {
      await route.continue();
    } catch {
      // The fixed app already aborted this stale request.
    }
  });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect.poll(() => logoutHeld).toBe(true);
  await expect(page).toHaveURL(/\/login$/);

  await signInHere(page, SWITCH_B, SWITCH_PASSWORD);
  expect(releaseLogout).not.toBeNull();
  releaseLogout?.();
  await page.waitForTimeout(750);

  // The old request may only produce a real server response now, after B's
  // login. In-memory B still looks fine; the cookie damage appears on reload.
  await expect(page).toHaveURL(/\/(overview|patients)$/);
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.reload();
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  const menu = page.getByRole("menu");
  await expect(menu).toContainText(SWITCH_B);
  await expect(menu).not.toContainText(SWITCH_A);
});

type RefreshTag = string;

async function refreshTag(page: Page): Promise<RefreshTag> {
  const cookies = await page.context().cookies([`${API}/api/v1/auth/`]);
  const value = cookies.find((cookie) => cookie.name === "clinicopus_refresh")?.value;
  if (!value) return "absent";
  const payload = JSON.parse(Buffer.from(value.split(".")[0], "base64url").toString()) as {
    sub?: string;
  };
  return String(payload.sub ?? "unknown").slice(0, 8);
}

type FetchPaused = {
  requestId: string;
  url: string;
  responseStatusCode?: number;
  responseHeaders?: Array<{ name: string; value: string }>;
};

test("S-42 a late refresh response cannot overwrite the new user's cookie", async ({
  page,
}) => {
  test.setTimeout(120_000);
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);

  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const aTag = await refreshTag(page);
  expect(aTag).not.toBe("absent");

  // Hold the refresh RESPONSE after the server produced A's rotated cookie.
  // CDP Fetch exposes response headers but hides Set-Cookie, so capture the
  // real Set-Cookie from Network.responseReceivedExtraInfo and replay it with
  // Fetch.continueRequest. route.fulfill() is not used because it cannot apply
  // cookies to the browser jar.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*api/v1/auth/refresh/*", requestStage: "Response" }],
  });
  type ExtraInfo = { requestId: string; headers: Record<string, string> };
  let responseReady = false;
  let heldRequestId: string | null = null;
  let heldResponseHeaders: Array<{ name: string; value: string }> = [];
  let rotatedSetCookie = "";
  let captureRotatedCookie = true;
  let releaseResponse: (() => void) | null = null;
  const markReady = () => {
    if (heldRequestId && rotatedSetCookie) responseReady = true;
  };
  cdp.on("Network.responseReceivedExtraInfo", (event: ExtraInfo) => {
    const cookie = Object.entries(event.headers).find(
      ([name]) => name.toLowerCase() === "set-cookie",
    )?.[1];
    if (captureRotatedCookie && cookie?.includes("clinicopus_refresh=")) {
      rotatedSetCookie = cookie;
      const token = /clinicopus_refresh="?([^;"]+)"?/.exec(cookie)?.[1] ?? "";
      console.log("ROTATED_TAG", token ? JSON.parse(Buffer.from(token.split(".")[0], "base64url").toString()).sub.slice(0, 8) : "none");
    }
    markReady();
  });
  cdp.on("Fetch.requestPaused", (event: FetchPaused) => {
    void (async () => {
      try {
        if (!event.responseStatusCode) {
          await cdp.send("Fetch.continueRequest", { requestId: event.requestId });
          return;
        }
        if (heldRequestId) {
          await cdp.send("Fetch.continueRequest", { requestId: event.requestId });
          return;
        }
        heldRequestId = event.requestId;
        heldResponseHeaders = event.responseHeaders ?? [];
        markReady();
        await new Promise<void>((resolve) => {
          releaseResponse = resolve;
        });
        const responseHeaders = heldResponseHeaders.filter(
          (header) => header.name.toLowerCase() !== "set-cookie",
        );
        if (rotatedSetCookie) {
          responseHeaders.push({ name: "set-cookie", value: rotatedSetCookie });
        }
        await cdp.send("Fetch.continueRequest", {
          requestId: event.requestId,
          responseCode: event.responseStatusCode,
          responseHeaders,
        });
        // This harness's Fetch.continueRequest does not re-apply Set-Cookie, so
        // replay the exact server-produced cookie into the browser's jar. No
        // pre-release cookie is changed and the value comes only from the real
        // 200 refresh response captured above.
        const rotatedValue = /clinicopus_refresh="?([^;"]+)"?/.exec(rotatedSetCookie)?.[1];
        if (rotatedValue) {
          await cdp.send("Network.setCookie", {
            name: "clinicopus_refresh",
            value: rotatedValue,
            url: `${API}/api/v1/auth/`,
            httpOnly: true,
            sameSite: "Lax",
          });
        }
      } catch {
        // The fixed app aborted the stale request, so no response is delivered.
      }
    })();
  });

  let forced = false;
  await page.route("**/api/v1/patients/?q=*", async (route) => {
    if (!forced) {
      forced = true;
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Access token is revoked or expired." }),
      });
      return;
    }
    await route.continue();
  });

  // Trigger a real 401 through the app's own query so api.ts starts a refresh
  // while A's workspace is still mounted.
  await steadyFill(page, "Search by name, phone, or patient number", "S42");
  await expect.poll(() => responseReady).toBe(true);
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  captureRotatedCookie = false;
  await signInHere(page, SWITCH_B, SWITCH_PASSWORD);
  const beforeTag = await refreshTag(page);
  console.log("BEFORE_TAG", aTag, beforeTag);
  expect(beforeTag).not.toBe(aTag);

  // Release the server-produced A refresh response; the browser applies its
  // real Set-Cookie if the app failed to abort the stale request.
  expect(releaseResponse).not.toBeNull();
  releaseResponse?.();
  await page.waitForTimeout(750);
  await cdp.send("Fetch.disable").catch(() => undefined);
  await cdp.send("Network.disable").catch(() => undefined);

  const afterTag = await refreshTag(page);
  console.log("AFTER_TAG", beforeTag, afterTag);
  expect(afterTag).toBe(beforeTag);
  await expect(page).toHaveURL(/\/(overview|patients)$/);
  await page.reload();
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  const menu = page.getByRole("menu");
  await expect(menu).toContainText(SWITCH_B);
  await expect(menu).not.toContainText(SWITCH_A);
});

test("S-42 fallback marker cookie outlives the still-valid refresh cookie", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("localStorage writes are blocked");
    };
  });
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);

  let releaseLogout: (() => void) | null = null;
  await page.route("**/api/v1/auth/logout/", async (route) => {
    await new Promise<void>((resolve) => {
      releaseLogout = resolve;
    });
    await route.abort("failed");
  });

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  releaseLogout?.();
  await page.waitForTimeout(500);

  const cookies = await page.context().cookies([`${API}/api/v1/auth/`]);
  const marker = cookies.find((cookie) => cookie.name === "klinklik_explicit_signin");
  const refresh = cookies.find((cookie) => cookie.name === "clinicopus_refresh");
  expect(marker).toBeTruthy();
  expect(refresh).toBeTruthy();
  const now = Date.now() / 1000;
  expect(marker!.expires).toBeGreaterThan(now + 24 * 60 * 60);
  expect(marker!.expires).toBeGreaterThanOrEqual(refresh!.expires);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test("S-42 sign-in clears both marker stores after local storage recovers", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      const scoped = window as Window & { __s42BlockMarkerWrites?: boolean };
      const markerKeys = ["klinklik:explicit-signin-required", "klinklik:logout-unconfirmed"];
      if (scoped.__s42BlockMarkerWrites && markerKeys.includes(String(key))) {
        throw new Error("marker localStorage write is blocked");
      }
      return original.call(this, key, value);
    };
  });
  ensureSwitchUsers();
  await loginAs(page, SWITCH_A, SWITCH_PASSWORD);

  await page.evaluate(() => {
    (window as Window & { __s42BlockMarkerWrites?: boolean }).__s42BlockMarkerWrites = true;
  });
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Switch user", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  const exitCookies = await page.context().cookies([API]);
  expect(exitCookies.find((cookie) => cookie.name === "klinklik_explicit_signin")).toBeTruthy();
  expect(
    await page.evaluate(() => window.localStorage.getItem("klinklik:explicit-signin-required")),
  ).toBeNull();

  await page.evaluate(() => {
    (window as Window & { __s42BlockMarkerWrites?: boolean }).__s42BlockMarkerWrites = false;
  });
  await signInHere(page, SWITCH_B, SWITCH_PASSWORD);

  expect(
    await page.evaluate(() => window.localStorage.getItem("klinklik:explicit-signin-required")),
  ).toBeNull();
  const signedInCookies = await page.context().cookies([API]);
  expect(signedInCookies.find((cookie) => cookie.name === "klinklik_explicit_signin")).toBeUndefined();
  expect(
    signedInCookies.find((cookie) => cookie.name === "klinklik_logout_unconfirmed"),
  ).toBeUndefined();

  await page.reload();
  await expect(page).toHaveURL(/\/(overview|patients)$/);
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(page.getByRole("menu")).toContainText(SWITCH_B);
});
