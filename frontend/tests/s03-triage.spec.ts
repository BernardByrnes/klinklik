import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
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

test("S-03 triage draft saves, resumes, completes and reaches the clinician", async ({
  page,
}) => {
  await login(page);
  const session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const lastName = `Triage${suffix}`;
  const patientName = `S03 ${lastName}`;

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: "S03",
      last_name: lastName,
      sex: "FEMALE",
      phone: `0703${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;

  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `s03-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string | null;
    patient_id: string;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  const visitContext = await page.request.get(
    `${API}/api/v1/reception/visits/${checkedIn.visit_id}/`,
    { headers: apiHeaders(session) }
  );
  expect(visitContext.ok()).toBeTruthy();
  const contextBody = (await visitContext.json()) as {
    patient: { id: string };
    allergy: { etag: string } | null;
  };
  expect(contextBody.allergy?.etag).toBeTruthy();
  const nka = await page.request.post(
    `${API}/api/v1/clinic/patients/${contextBody.patient.id}/allergy-status/`,
    {
      headers: {
        ...apiHeaders(session),
        "Idempotency-Key": `s03-allergy-${suffix}`,
        "If-Match": contextBody.allergy!.etag,
      },
      data: { status: "NKA" },
    }
  );
  expect(nka.ok(), await nka.text()).toBeTruthy();

  const invoicePosts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname === "/api/v1/billing/invoices/"
    ) {
      invoicePosts.push(request.url());
    }
  });

  const startPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/triage/${checkedIn.queue_id}/start/`) &&
      response.request().method() === "POST"
  );
  await page.goto(`/triage?entry=${checkedIn.queue_id}`);
  const startResponse = await startPromise;
  expect(startResponse.status(), await startResponse.text()).toBe(200);
  const started = (await startResponse.json()) as {
    triage_record: { id: string; state: string; version: number };
  };
  expect(started.triage_record.state).toBe("DRAFT");
  const recordId = started.triage_record.id;

  await steadyFill(page, "Chief complaint", "Synthetic S-03 fever");
  await steadyFill(page, "Temperature (°C)", "38.4");
  await steadyFill(page, "Pulse (bpm)", "92");
  await page.getByLabel("Priority", { exact: true }).selectOption("URGENT");

  const savePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/triage-records/${recordId}/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  const saveResponse = await savePromise;
  expect(saveResponse.status(), await saveResponse.text()).toBe(200);
  const saved = (await saveResponse.json()) as {
    triage_record: { version: number; state: string };
  };
  expect(saved.triage_record.state).toBe("DRAFT");
  expect(saved.triage_record.version).toBeGreaterThan(1);

  const resumePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/triage/${checkedIn.queue_id}/start/`) &&
      response.request().method() === "POST"
  );
  await page.reload();
  const resumeResponse = await resumePromise;
  expect(resumeResponse.status(), await resumeResponse.text()).toBe(200);
  const resumed = (await resumeResponse.json()) as {
    triage_record: { id: string; version: number; state: string };
  };
  expect(resumed.triage_record.id).toBe(recordId);
  expect(resumed.triage_record.state).toBe("DRAFT");
  await expect(page.getByLabel("Chief complaint", { exact: true })).toHaveValue(
    "Synthetic S-03 fever"
  );
  await expect(page.getByLabel("Temperature (°C)", { exact: true })).toHaveValue("38.4");
  await expect(page.getByLabel("Pulse (bpm)", { exact: true })).toHaveValue("92");

  const priority = page.getByLabel("Priority", { exact: true });
  await priority.focus();
  await expect(priority).toBeFocused();

  const completePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/triage-records/${recordId}/complete/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Complete triage" }).click();
  const completeResponse = await completePromise;
  expect(completeResponse.status(), await completeResponse.text()).toBe(200);
  const completed = (await completeResponse.json()) as {
    triage_record: { state: string; current_version: number; acuity: string };
    source_queue_entry_id: string;
    source_state: string;
    destination_queue_entry_id: string;
    destination_state: string;
  };
  expect(completed.triage_record.state).toBe("COMPLETED");
  expect(completed.triage_record.current_version).toBe(1);
  expect(completed.triage_record.acuity).toBe("URGENT");
  expect(completed.source_queue_entry_id).toBe(checkedIn.queue_id);
  expect(completed.source_state).toBe("COMPLETED");
  expect(completed.destination_state).toBe("WAITING");
  await expect(page.getByText(`Triage recorded for ${patientName}`)).toBeVisible();
  expect(invoicePosts).toEqual([]);

  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const consultRow = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(consultRow).toBeVisible();
  await consultRow.click();

  const encounterPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const encounterResponse = await encounterPromise;
  expect(encounterResponse.status(), await encounterResponse.text()).toBe(201);
  const encounter = (await encounterResponse.json()) as {
    visit: string;
    queue_entry: string;
  };
  expect(encounter.visit).toBe(checkedIn.visit_id);
  expect(encounter.queue_entry).toBe(completed.destination_queue_entry_id);

  await page.getByRole("tab", { name: "History" }).click();
  const summary = page.getByTestId("triage-summary");
  await expect(summary).toBeVisible();
  await expect(summary).toContainText("URGENT");
  await expect(summary).toContainText("Synthetic S-03 fever");
  await expect(summary).toContainText("38.4");
  await expect(summary).toContainText("Read-only");
});
