import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(150);
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

test("S-04 opens the same Visit Encounter, saves, resumes and signs once", async ({ page }) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const lastName = `Synthetic${suffix}`;
  const patientName = `S04 ${lastName}`;

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: "S04",
      last_name: lastName,
      sex: "FEMALE",
      phone: `078${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `s04-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string | null;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  // Complete triage through the admitted legacy route; the Encounter journey
  // starts from the resulting consultation destination.
  const triageWorklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=TRIAGE&state=WAITING,CALLED`,
    { headers: apiHeaders(session) }
  );
  expect(triageWorklist.ok()).toBeTruthy();
  const triageRows = (await triageWorklist.json()) as {
    entries: Array<{ id: string; visit_id: string | null; version: number }>;
  };
  const triageRow = triageRows.entries.find((row) => row.id === checkedIn.queue_id);
  expect(triageRow).toBeTruthy();
  const triage = await page.request.post(
    `${API}/api/v1/clinic/triage/${triageRow!.id}/`,
    {
      headers: {
        ...apiHeaders(session),
        "If-Match": `"${triageRow!.version}"`,
        "Idempotency-Key": `s04-triage-${suffix}`,
      },
      data: {
        expected_version: triageRow!.version,
        acuity: "ROUTINE",
        chief_complaint: "S04 synthetic triage complaint",
      },
    }
  );
  expect(triage.status(), await triage.text()).toBe(201);

  const consultationWorklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=WAITING`,
    { headers: apiHeaders(session) }
  );
  const consultationRows = (await consultationWorklist.json()) as {
    entries: Array<{ id: string; visit_id: string | null }>;
  };
  const destination = consultationRows.entries.find(
    (row) => row.visit_id === checkedIn.visit_id
  );
  expect(destination).toBeTruthy();

  await page.goto("/consultations");
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const encounterPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const encounterResponse = await encounterPromise;
  expect(encounterResponse.status()).toBe(201);
  const encounter = (await encounterResponse.json()) as {
    id: string;
    visit: string;
    queue_entry: string;
  };
  expect(encounter.visit).toBe(checkedIn.visit_id);
  expect(encounter.queue_entry).toBe(destination!.id);

  const reviewResponse = page.waitForResponse(
    (response) => response.url().endsWith("/allergies/review/") && response.status() === 200
  );
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", "S04 synthetic no final diagnosis");
  await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
  await expect(page.getByTestId("no-diagnosis-state")).toBeVisible();
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
  const disposition = page.waitForResponse(
    (response) => response.url().endsWith("/disposition/") && response.status() === 200
  );
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  await disposition;
  await page.getByRole("tab", { name: "History", exact: true }).click();

  await steadyFill(page, "Presenting complaint", "S04 synthetic chest pain");
  const savePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/encounters/${encounter.id}/notes/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await savePromise).status()).toBe(200);

  await page.reload();
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  const resumePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const resumed = (await (await resumePromise).json()) as { id: string };
  expect(resumed.id).toBe(encounter.id);
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue(
    "S04 synthetic chest pain"
  );

  const invoicePosts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname === "/api/v1/billing/invoices/"
    ) {
      invoicePosts.push(request.url());
    }
  });
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  const signPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/encounters/${encounter.id}/sign/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  expect((await signPromise).status()).toBe(200);
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
  expect(invoicePosts).toEqual([]);

  const finalSession = await apiLogin(page);
  const completed = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=COMPLETED`,
    { headers: apiHeaders(finalSession) }
  );
  const completedRows = (await completed.json()) as {
    entries: Array<{ id: string; visit_id: string | null }>;
  };
  expect(
    completedRows.entries.find((row) => row.id === destination!.id)
  ).toBeTruthy();
});
