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
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

async function expectNamedControls(page: Page) {
  const unnamedControls = await page.locator("button, input, select, textarea, a").evaluateAll((controls) =>
    controls
      .filter((control) => {
        const element = control as HTMLElement;
        const labelledBy = element.getAttribute("aria-labelledby");
        const labelled = element.getAttribute("aria-label") || element.getAttribute("title");
        const associatedLabel = element.id
          ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)?.textContent
          : null;
        return !labelledBy && !labelled && !associatedLabel?.trim() && !element.textContent?.trim();
      })
      .map((control) => control.outerHTML),
  );
  expect(unnamedControls).toEqual([]);
}

test("S-02 queue exposes canonical status filters and a keyboard focus path", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/queue");

  await expect(page.getByRole("heading", { name: "Queue", exact: true })).toBeVisible();
  await expect(page.getByRole("tablist", { name: "Queue status filter", exact: true })).toBeVisible();
  for (const name of ["All", "Awaiting triage", "In service", "Completed stage", "In service (consultation)"]) {
    await expect(page.getByRole("tab", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByLabel("Filter queue", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Queue entries/ })).toBeVisible();
  await expectNamedControls(page);

  const triageTab = page.getByRole("tab", { name: "Awaiting triage", exact: true });
  await triageTab.focus();
  await expect(triageTab).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tab", { name: "In service", exact: true })).toBeFocused();
});

test("S-02 triage renders its accessible empty and selection states", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/triage");

  await expect(page.getByRole("heading", { name: "Triage", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Awaiting triage/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Triage record", exact: true })).toBeVisible();
  await expect(page.getByText("No patient selected.", { exact: true })).toBeVisible();
  await expectNamedControls(page);
});

test("S-02 check-in, call, triage and encounter keep one Visit handoff", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);

  // Reception: register and check in one synthetic patient.
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/\/patients$/);
  const suffix = Date.now().toString().slice(-6);
  const patientName = `Handoff Patient${suffix}`;
  await steadyFill(page, "First name", "Handoff");
  await steadyFill(page, "Last name", `Patient${suffix}`);
  await steadyFill(page, "Phone", "0701" + suffix);
  await page.locator("form").getByRole("button", { name: "Register patient" }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible();

  const invoiceCreatePosts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/billing/invoices/") {
      invoiceCreatePosts.push(request.url());
    }
  });

  const checkInPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/reception/visits/check-in/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Check in patient" }).click();
  const checkInResponse = await checkInPromise;
  expect(checkInResponse.status()).toBe(201);
  const checkIn = (await checkInResponse.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string | null;
  };
  expect(checkIn.invoice_id).toBeTruthy();
  const visitId = checkIn.visit_id;
  const triageQueueId = checkIn.queue_id;

  // The canonical triage record requires an explicit patient allergy status.
  const apiSession = await apiLogin(page);
  const visitContext = await page.request.get(`${API}/api/v1/reception/visits/${visitId}/`, {
    headers: apiHeaders(apiSession),
  });
  expect(visitContext.ok()).toBeTruthy();
  const contextBody = (await visitContext.json()) as {
    patient: { id: string };
    allergy: { etag: string } | null;
  };
  expect(contextBody.allergy?.etag).toBeTruthy();
  const allergy = await page.request.post(
    `${API}/api/v1/clinic/patients/${contextBody.patient.id}/allergy-status/`,
    {
      headers: {
        ...apiHeaders(apiSession),
        "If-Match": contextBody.allergy!.etag,
        "Idempotency-Key": `s02-allergy-${suffix}`,
      },
      data: { status: "NKA" },
    }
  );
  expect(allergy.ok(), await allergy.text()).toBeTruthy();

  // Queue: the operational worklist is live and the exact call claims the row.
  const queueResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/queue/operational/") &&
      response.request().method() === "GET",
  );
  await page.locator('nav a[href="/queue"]').click();
  await expect(page).toHaveURL(/\/queue$/);
  const queueResponse = await queueResponsePromise;
  expect(queueResponse.status()).toBe(200);

  await page.getByLabel("Filter queue").fill(patientName);
  const queueRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(queueRow).toBeVisible();
  const callPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/queue/${triageQueueId}/call/`) &&
      response.request().method() === "POST",
  );
  await queueRow.getByRole("button", { name: "Claim" }).click();
  const callResponse = await callPromise;
  expect(callResponse.status()).toBe(200);
  const called = (await callResponse.json()) as { state: string; version: number };
  expect(called.state).toBe("CALLED");
  await expect(queueRow.getByText("Called", { exact: true })).toBeVisible();

  // Triage: human-selected acuity completes the source row.
  await queueRow.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/triage/);
  await expect(page.getByText(patientName).first()).toBeVisible();
  await steadyFill(page, "Chief complaint", "Synthetic S-02 handoff complaint");
  await steadyFill(page, "Pulse (bpm)", "78");
  await page.getByLabel("Priority", { exact: true }).selectOption("URGENT");
  const triagePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/complete/") &&
      response.url().includes("/triage-records/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Complete triage" }).click();
  const triageResponse = await triagePromise;
  expect(triageResponse.status()).toBe(200);
  const triageBody = (await triageResponse.json()) as {
    triage_record: { state: string };
    source_state: string;
  };
  expect(triageBody.triage_record.state).toBe("COMPLETED");
  expect(triageBody.source_state).toBe("COMPLETED");
  await expect(page.getByText("Triage recorded for " + patientName)).toBeVisible();

  // Consultation: the worklist offers the waiting destination for the same Visit.
  const worklistPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/queue/operational/") &&
      response.url().includes("queue_type=CONSULTATION") &&
      response.status() === 200,
  );
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const worklist = (await (await worklistPromise).json()) as {
    entries: Array<{ id: string; visit_id: string | null; state: string }>;
  };
  const destination = worklist.entries.find((entry) => entry.visit_id === visitId);
  expect(destination).toBeTruthy();
  expect(destination!.id).not.toBe(triageQueueId);
  expect(destination!.state).toBe("WAITING");

  const consultRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(consultRow).toBeVisible();
  await consultRow.click();

  const refreshedWorklistPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/queue/operational/") &&
      response.url().includes("queue_type=CONSULTATION") &&
      response.status() === 200,
  );
  const encounterPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const encounterResponse = await encounterPromise;
  expect(encounterResponse.status()).toBe(201);
  const encounter = (await encounterResponse.json()) as {
    visit: string;
    queue_entry: string;
  };
  expect(encounter.visit).toBe(visitId);
  expect(encounter.queue_entry).toBe(destination!.id);

  const refreshedWorklist = (await (await refreshedWorklistPromise).json()) as {
    entries: Array<{ id: string; state: string }>;
  };
  expect(refreshedWorklist.entries.find((entry) => entry.id === destination!.id)?.state).toBe(
    "IN_SERVICE",
  );

  // The handoff never creates a second consultation charge.
  expect(invoiceCreatePosts).toEqual([]);
});

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function apiLogin(page: Page) {
  const response = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  return {
    token: body.access_token,
    facilityId: body.facilities[0].id,
  };
}

function apiHeaders(session: { token: string; facilityId: string }) {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Facility-Id": session.facilityId,
    "Content-Type": "application/json",
  };
}

async function triagedConsultationRow(page: Page, session: { token: string; facilityId: string }) {
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: "Edge",
      last_name: `Consult${suffix}`,
      sex: "FEMALE",
      phone: `0702${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `edge-ci-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as { visit_id: string; queue_id: string };

  const worklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=TRIAGE&state=WAITING`,
    { headers: apiHeaders(session) },
  );
  const source = (await worklist.json()) as { entries: Array<{ id: string; version: number }> };
  const sourceRow = source.entries.find((row) => row.id === checkedIn.queue_id);
  expect(sourceRow).toBeTruthy();

  const triage = await page.request.post(`${API}/api/v1/clinic/triage/${sourceRow!.id}/`, {
    headers: {
      ...apiHeaders(session),
      "If-Match": `"${sourceRow!.version}"`,
      "Idempotency-Key": `edge-triage-${suffix}`,
    },
    data: {
      expected_version: sourceRow!.version,
      acuity: "ROUTINE",
      chief_complaint: "Synthetic consultation edge",
    },
  });
  expect(triage.status(), await triage.text()).toBe(201);

  const consultation = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=WAITING`,
    { headers: apiHeaders(session) },
  );
  const rows = (await consultation.json()) as {
    entries: Array<{ id: string; visit_id: string | null; version: number }>;
  };
  const destination = rows.entries.find((row) => row.visit_id === checkedIn.visit_id);
  expect(destination).toBeTruthy();
  return { destination: destination!, visitId: checkedIn.visit_id, suffix };
}

test("S-02 retryable encounter result keeps the same idempotency key and payload", async ({
  page,
}) => {
  const session = await apiLogin(page);
  const { destination } = await triagedConsultationRow(page, session);

  const keys: string[] = [];
  const bodies: string[] = [];
  let attempt = 0;
  await page.route(/\/api\/v1\/clinic\/encounters\/$/, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    keys.push(route.request().headers()["idempotency-key"] ?? "");
    bodies.push(route.request().postData() ?? "");
    attempt += 1;
    if (attempt === 1) {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          code: "IDEMPOTENCY_IN_PROGRESS",
          detail: "The idempotent request is still being completed.",
          retryable: true,
        }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto(`/consultations?entry=${destination.id}`);
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByText(/still being completed/)).toBeVisible();
  // The intent is retained, so the action stays available for the same key.
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeEnabled();
  await page.getByRole("button", { name: "Start encounter" }).click();

  await expect.poll(() => keys.length).toBe(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  expect(bodies[1]).toBe(bodies[0]);
});

test("S-02 a failed worklist refresh blocks Start until the row is confirmed", async ({ page }) => {
  const session = await apiLogin(page);
  const { destination } = await triagedConsultationRow(page, session);

  let failWorklist = false;
  await page.route(/\/api\/v1\/clinic\/queue\/operational\//, async (route) => {
    if (failWorklist) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ code: "MIGRATION_TARGET_DISABLED", detail: "unavailable" }),
      });
      return;
    }
    await route.continue();
  });

  let conflict = true;
  await page.route(/\/api\/v1\/clinic\/encounters\/$/, async (route) => {
    if (route.request().method() === "POST" && conflict) {
      conflict = false;
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ code: "VERSION_CONFLICT", detail: "The queue entry changed." }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto(`/consultations?entry=${destination.id}`);
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();

  // A definitive conflict asks for a refreshed row; that refresh fails here.
  failWorklist = true;
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByText("The consultation queue could not be loaded.")).toBeVisible();
  // The cached row may still be on screen, but it cannot submit while the
  // scoped worklist is unavailable.
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeDisabled();

  // Restoring the worklist restores a confirmed row and a usable action.
  failWorklist = false;
  await page.getByRole("button", { name: "Retry" }).click();
  const row = page.getByRole("listitem").filter({ hasText: "Edge Consult" });
  await expect(row.first()).toBeVisible();
  await row.first().click();
  await expect(page.getByRole("button", { name: "Start encounter" })).toBeEnabled();
});
