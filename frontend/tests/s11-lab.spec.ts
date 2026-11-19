import { expect, request, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const ADMIN_PASSWORD = "ClinicopusDemo123!";
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

async function apiLogin(page: Page, username: string, password: string) {
  const response = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username, password },
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

test("S-11 orders from the Encounter, collects, releases and exposes the result", async ({
  page,
}) => {
  await login(page);
  let session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S11",
      last_name: `Lab${suffix}`,
      sex: "FEMALE",
      phone: `075${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s11-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string | null;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  const context = await page.request.get(
    `${API}/api/v1/reception/visits/${checkedIn.visit_id}/`,
    { headers: headers(session) }
  );
  const contextBody = (await context.json()) as {
    allergy: { etag: string } | null;
  };
  const nka = await page.request.post(
    `${API}/api/v1/clinic/patients/${patientId}/allergy-status/`,
    {
      headers: {
        ...headers(session),
        "Idempotency-Key": `s11-nka-${suffix}`,
        "If-Match": contextBody.allergy!.etag,
      },
      data: { status: "NKA" },
    }
  );
  expect(nka.ok(), await nka.text()).toBeTruthy();
  const queueList = (await (
    await page.request.get(`${API}/api/v1/clinic/queue/`, { headers: headers(session) })
  ).json()) as Array<{ id: string; version: number }>;
  const queueRow = queueList.find((entry) => entry.id === checkedIn.queue_id);
  expect(queueRow).toBeTruthy();
  const triage = await page.request.post(
    `${API}/api/v1/clinic/triage/${checkedIn.queue_id}/`,
    {
      headers: {
        ...headers(session),
        "Idempotency-Key": `s11-triage-${suffix}`,
        "If-Match": `"${queueRow!.version}"`,
      },
      data: { acuity: "ROUTINE", chief_complaint: "Synthetic S11 lab complaint" },
    }
  );
  expect(triage.ok(), await triage.text()).toBeTruthy();

  await page.goto("/consultations");
  const row = page.getByRole("listitem").filter({ hasText: `S11 Lab${suffix}` });
  await expect(row).toBeVisible();
  await row.click();
  const encounterPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const encounter = (await (await encounterPromise).json()) as { id: string };

  session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const servicesResponse = await page.request.get(`${API}/api/v1/billing/services/`, {
    headers: headers(session),
  });
  expect(servicesResponse.ok(), await servicesResponse.text()).toBeTruthy();
  const services = (await servicesResponse.json()) as Array<{ id: string }>;
  const labTest = await page.request.post(`${API}/api/v1/lab/tests/`, {
    headers: headers(session),
    data: {
      code: `S11-${suffix}`,
      name: `Synthetic S11 lab ${suffix}`,
      service_id: services[0].id,
      result_type: "PANEL",
      analytes: [
        {
          code: "HB",
          name: "Haemoglobin",
          unit: "g/dL",
          result_type: "NUMERIC",
          sanity_min: "0",
          sanity_max: "250",
          range: { low: "4", high: "11" },
        },
      ],
    },
  });
  expect(labTest.ok(), await labTest.text()).toBeTruthy();
  const testBody = (await labTest.json()) as {
    id: string;
    analytes: Array<{ id: string }>;
  };
  const order = await page.request.post(`${API}/api/v1/lab/orders/`, {
    headers: { ...headers(session), "Idempotency-Key": `s11-order-${suffix}` },
    data: { encounter_id: encounter.id, test_ids: [testBody.id], priority: "URGENT" },
  });
  expect(order.ok(), await order.text()).toBeTruthy();
  const orderBody = (await order.json()) as { items: Array<{ id: string }> };
  const itemId = orderBody.items[0].id;

  await page.goto("/lab");
  await expect(page.getByRole("heading", { name: "Laboratory" })).toBeVisible();
  await expect(page.getByText("URGENT").first()).toBeVisible();
  const collected = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${itemId}/collect/`) &&
      response.request().method() === "POST"
  );
  await page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S11 lab ${suffix}` })
    .getByRole("button", { name: "Collect sample", exact: true })
    .click();
  expect((await collected).status()).toBe(200);

  // Results are entered by a second authorized user in an isolated API
  // context; the browser session must stay on the demo owner for release.
  const adminApi = await request.newContext();
  const adminLogin = await adminApi.post(`${API}/api/v1/auth/login/`, {
    data: { username: "admin@clinicopus.local", password: ADMIN_PASSWORD },
  });
  expect(adminLogin.ok()).toBeTruthy();
  const adminBody = (await adminLogin.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  const admin = { token: adminBody.access_token, facilityId: adminBody.facilities[0].id };
  const entered = await adminApi.patch(
    `${API}/api/v1/lab/items/${itemId}/results/`,
    {
      headers: { ...headers(admin), "Idempotency-Key": `s11-result-${suffix}` },
      data: {
        values: [{ analyte_id: testBody.analytes[0].id, value: "13.2" }],
        complete: true,
      },
    }
  );
  expect(entered.ok(), await entered.text()).toBeTruthy();
  await adminApi.dispose();

  await page.reload();
  await expect(
    page
      .getByRole("listitem")
      .filter({ hasText: `Synthetic S11 lab ${suffix}` })
      .getByRole("button", { name: "Release result" })
  ).toBeVisible();
  const released = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${itemId}/release/`) &&
      response.request().method() === "POST"
  );
  await page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S11 lab ${suffix}` })
    .getByRole("button", { name: "Release result", exact: true })
    .click();
  const releaseResponse = await released;
  expect(releaseResponse.status(), await releaseResponse.text()).toBe(200);
  await expect(page.getByText("Laboratory state updated.")).toBeVisible();
  session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const results = await page.request.get(
    `${API}/api/v1/lab/encounters/${encounter.id}/results/`,
    { headers: headers(session) }
  );
  expect(results.ok()).toBeTruthy();
  const resultBody = (await results.json()) as {
    results: Array<{ values: Array<{ value: string; flag: string }> }>;
  };
  expect(resultBody.results[0].values[0].value).toBe("13.2");
  expect(resultBody.results[0].values[0].flag).toBe("HIGH");
});
