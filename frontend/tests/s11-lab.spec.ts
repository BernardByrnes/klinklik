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
  const verifyRow = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S11 lab ${suffix}` });
  await expect(
    verifyRow.getByRole("button", { name: "Review and release" })
  ).toBeVisible();
  await verifyRow.getByRole("button", { name: "Review and release", exact: true }).click();
  const released = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${itemId}/release/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Verify & release", exact: true }).click();
  const releaseResponse = await released;
  expect(releaseResponse.status(), await releaseResponse.text()).toBe(200);
  await expect(page.getByText("Result released to the ordering clinician.")).toBeVisible();
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

test("S-29-R1 limited lab technician sees the verification queue without release authority", async ({
  page,
}) => {
  await login(page);
  let session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S29R1",
      last_name: `Lab${suffix}`,
      sex: "FEMALE",
      phone: `075${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok(), await patient.text()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s29-r1-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string | null;
  };

  const context = await page.request.get(
    `${API}/api/v1/reception/visits/${checkedIn.visit_id}/`,
    { headers: headers(session) }
  );
  const contextBody = (await context.json()) as { allergy: { etag: string } | null };
  const nka = await page.request.post(
    `${API}/api/v1/clinic/patients/${patientId}/allergy-status/`,
    {
      headers: {
        ...headers(session),
        "Idempotency-Key": `s29-r1-nka-${suffix}`,
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
        "Idempotency-Key": `s29-r1-triage-${suffix}`,
        "If-Match": `"${queueRow!.version}"`,
      },
      data: { acuity: "ROUTINE", chief_complaint: "Synthetic S29 R1 complaint" },
    }
  );
  expect(triage.ok(), await triage.text()).toBeTruthy();

  await page.goto("/consultations");
  const row = page.getByRole("listitem").filter({ hasText: `S29R1 Lab${suffix}` });
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
  const services = (await servicesResponse.json()) as Array<{ id: string }>;
  const labTest = await page.request.post(`${API}/api/v1/lab/tests/`, {
    headers: headers(session),
    data: {
      code: `S29R1-${suffix}`,
      name: `Synthetic S29 R1 lab ${suffix}`,
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
  const testBody = (await labTest.json()) as { id: string; analytes: Array<{ id: string }> };
  const order = await page.request.post(`${API}/api/v1/lab/orders/`, {
    headers: { ...headers(session), "Idempotency-Key": `s29-r1-order-${suffix}` },
    data: { encounter_id: encounter.id, test_ids: [testBody.id], priority: "ROUTINE" },
  });
  expect(order.ok(), await order.text()).toBeTruthy();
  const itemId = ((await order.json()) as { items: Array<{ id: string }> }).items[0].id;
  const collected = await page.request.post(
    `${API}/api/v1/lab/items/${itemId}/collect/`,
    {
      headers: { ...headers(session), "Idempotency-Key": `s29-r1-collect-${suffix}` },
      data: {},
    }
  );
  expect(collected.ok(), await collected.text()).toBeTruthy();

  const adminLogin = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "admin@clinicopus.local", password: ADMIN_PASSWORD },
  });
  expect(adminLogin.ok(), await adminLogin.text()).toBeTruthy();
  const adminBody = (await adminLogin.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  const admin = { token: adminBody.access_token, facilityId: adminBody.facilities[0].id };
  const entered = await page.request.patch(
    `${API}/api/v1/lab/items/${itemId}/results/`,
    {
      headers: { ...headers(admin), "Idempotency-Key": `s29-r1-result-${suffix}` },
      data: {
        values: [{ analyte_id: testBody.analytes[0].id, value: "13.2" }],
        complete: true,
      },
    }
  );
  expect(entered.ok(), await entered.text()).toBeTruthy();

  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await steadyFill(page, "Username", "labtech@clinicopus.local");
  await steadyFill(page, "Password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("link", { name: "Laboratory" })).toBeVisible();

  await page.goto("/lab");
  const verifyRow = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S29 R1 lab ${suffix}` });
  await expect(verifyRow).toBeVisible();
  const releaseButton = verifyRow.getByRole("button", { name: "Review and release", exact: true });
  await expect(releaseButton).toBeDisabled();
  await expect(
    verifyRow.getByText("A separate authorized verifier must release this result.")
  ).toBeVisible();

  const techSession = await apiLogin(page, "labtech@clinicopus.local", ADMIN_PASSWORD);
  const forcedRelease = await page.request.post(
    `${API}/api/v1/lab/items/${itemId}/release/`,
    {
      headers: { ...headers(techSession), "Idempotency-Key": `s29-r1-forced-${suffix}` },
      data: {},
    }
  );
  expect(forcedRelease.status()).toBe(403);
});

async function s30SetupLabItem(
  page: Page,
  session: { token: string; facilityId: string },
  suffix: string,
  options: { action: "collect" | "enter" | "reject"; priority?: "ROUTINE" | "URGENT" },
) {
  const services = (await (
    await page.request.get(`${API}/api/v1/billing/services/`, { headers: headers(session) })
  ).json()) as Array<{ id: string }>;

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S30",
      last_name: `Lab${suffix}`,
      sex: "FEMALE",
      phone: `075${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok(), await patient.text()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const patientName = `S30 Lab${suffix}`;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s30-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as { visit_id: string; queue_id: string };

  const context = await page.request.get(
    `${API}/api/v1/reception/visits/${checkedIn.visit_id}/`,
    { headers: headers(session) }
  );
  const contextBody = (await context.json()) as { allergy: { etag: string } | null };
  const nka = await page.request.post(
    `${API}/api/v1/clinic/patients/${patientId}/allergy-status/`,
    {
      headers: {
        ...headers(session),
        "Idempotency-Key": `s30-nka-${suffix}`,
        "If-Match": contextBody.allergy!.etag,
      },
      data: { status: "NKA" },
    }
  );
  expect(nka.ok(), await nka.text()).toBeTruthy();
  const queueRows = (await (
    await page.request.get(`${API}/api/v1/clinic/queue/`, { headers: headers(session) })
  ).json()) as Array<{ id: string; version: number }>;
  const queueRow = queueRows.find((row) => row.id === checkedIn.queue_id);
  expect(queueRow).toBeTruthy();
  const triage = await page.request.post(
    `${API}/api/v1/clinic/triage/${checkedIn.queue_id}/`,
    {
      headers: {
        ...headers(session),
        "If-Match": `"${queueRow!.version}"`,
        "Idempotency-Key": `s30-triage-${suffix}`,
      },
      data: {
        expected_version: queueRow!.version,
        acuity: "ROUTINE",
        chief_complaint: "Synthetic S30 lab complaint",
      },
    }
  );
  expect(triage.status(), await triage.text()).toBe(201);

  await page.goto("/consultations");
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  const encounterPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/clinic/encounters/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Start encounter" }).click();
  const encounter = (await (await encounterPromise).json()) as { id: string };

  session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const labTest = await page.request.post(`${API}/api/v1/lab/tests/`, {
    headers: headers(session),
    data: {
      code: `S30-${suffix}`,
      name: `Synthetic S30 lab ${suffix}`,
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
        {
          code: "WBC",
          name: "White cell count",
          unit: "x10^9/L",
          result_type: "NUMERIC",
          sanity_min: "0",
          sanity_max: "100",
          range: { low: "4", high: "11" },
        },
      ],
    },
  });
  expect(labTest.ok(), await labTest.text()).toBeTruthy();
  const testBody = (await labTest.json()) as {
    id: string;
    analytes: Array<{ id: string; code: string }>;
  };
  const order = await page.request.post(`${API}/api/v1/lab/orders/`, {
    headers: { ...headers(session), "Idempotency-Key": `s30-order-${suffix}` },
    data: {
      encounter_id: encounter.id,
      test_ids: [testBody.id],
      priority: options.priority ?? "ROUTINE",
    },
  });
  expect(order.ok(), await order.text()).toBeTruthy();
  const itemId = ((await order.json()) as { items: Array<{ id: string }> }).items[0].id;
  const collected = await page.request.post(
    `${API}/api/v1/lab/items/${itemId}/collect/`,
    {
      headers: { ...headers(session), "Idempotency-Key": `s30-collect-${suffix}` },
      data: {},
    }
  );
  expect(collected.ok(), await collected.text()).toBeTruthy();

  if (options.action === "collect") {
    // The browser test enters the result through the bench UI.
  } else if (options.action === "reject") {
    const rejected = await page.request.post(
      `${API}/api/v1/lab/items/${itemId}/reject/`,
      {
        headers: { ...headers(session), "Idempotency-Key": `s30-reject-${suffix}` },
        data: { reason: "Synthetic haemolysed sample" },
      }
    );
    expect(rejected.ok(), await rejected.text()).toBeTruthy();
  } else {
    const saved = await page.request.patch(
      `${API}/api/v1/lab/items/${itemId}/results/`,
      {
        headers: { ...headers(session), "Idempotency-Key": `s30-result-${suffix}` },
        data: {
          values: testBody.analytes.map((analyte, index) => ({
            analyte_id: analyte.id,
            value: index === 0 ? "13.2" : "6.0",
          })),
          complete: true,
        },
      }
    );
    expect(saved.ok(), await saved.text()).toBeTruthy();
  }
  return { patientName, encounter, itemId, testBody };
}

async function s30SwitchUser(page: Page, username: string, password: string) {
  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/(overview|consultations)$/);
}

test("S-30 technician enters results and a verifier releases the observed version", async ({
  page,
}) => {
  await login(page);
  const demo = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const setup = await s30SetupLabItem(page, demo, suffix, { action: "collect" });

  await s30SwitchUser(page, "labtech@clinicopus.local", ADMIN_PASSWORD);
  await page.goto("/lab");
  const benchRow = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S30 lab ${suffix}` });
  await expect(benchRow).toBeVisible();
  await benchRow.getByRole("button", { name: "Enter results", exact: true }).click();

  const hb = page.getByLabel(/Haemoglobin/).first();
  const wbc = page.getByLabel(/White cell count/).first();
  await expect(hb).toBeVisible();
  await expect(page.getByText(/g\/dL/).first()).toBeVisible();
  await hb.fill("251");
  await wbc.fill("6.0");
  const rangeError = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${setup.itemId}/results/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save results", exact: true }).click();
  expect((await rangeError).status()).toBe(422);
  await expect(page.getByText(/outside the sanity bounds/i)).toBeVisible();

  await hb.fill("13.2");
  await wbc.fill("6.0");
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${setup.itemId}/results/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save results", exact: true }).click();
  expect((await saved).status()).toBe(201);

  await s30SwitchUser(page, "admin@clinicopus.local", ADMIN_PASSWORD);
  await page.goto("/lab");
  const verifyRow = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S30 lab ${suffix}` });
  await verifyRow.getByRole("button", { name: "Review and release", exact: true }).click();
  await expect(page.getByText("13.2")).toBeVisible();
  await expect(page.getByText("HIGH")).toBeVisible();
  const verifierApi = await apiLogin(page, "admin@clinicopus.local", ADMIN_PASSWORD);
  const detail = await page.request.get(
    `${API}/api/v1/lab/items/${setup.itemId}/detail/`,
    { headers: headers(verifierApi) }
  );
  expect(detail.ok(), await detail.text()).toBeTruthy();
  const observed = (await detail.json()) as { version_no: number };
  const released = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/lab/items/${setup.itemId}/release/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Verify & release", exact: true }).click();
  const releaseResponse = await released;
  expect(releaseResponse.status()).toBe(200);
  expect(JSON.parse(releaseResponse.request().postData() ?? "{}").expected_version).toBe(
    observed.version_no
  );
  await expect(page.getByText(/result released/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Released/ })).toBeVisible();
});

test("S-30 rejected sample shows the safe reason and approved next action", async ({
  page,
}) => {
  await login(page);
  const demo = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  await s30SetupLabItem(page, demo, suffix, { action: "reject" });

  await s30SwitchUser(page, "labtech@clinicopus.local", ADMIN_PASSWORD);
  await page.goto("/lab");
  const rejectedRow = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S30 lab ${suffix}` });
  await expect(rejectedRow).toBeVisible();
  await expect(rejectedRow.getByText("Synthetic haemolysed sample")).toBeVisible();
  const recollect = rejectedRow.getByRole("button", { name: "Recollect sample", exact: true });
  await expect(recollect).toBeEnabled();
  const recollectResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/collect/") && response.request().method() === "POST"
  );
  await recollect.click();
  expect((await recollectResponse).status()).toBe(200);
});

test("S-30 clinician sees status only until release, then read-only results", async ({
  page,
}) => {
  await login(page);
  const demo = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const setup = await s30SetupLabItem(page, demo, suffix, { action: "enter" });

  await page.getByRole("tab", { name: "Investigations", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Investigations" })).toBeVisible();
  await expect(page.getByText("RESULT_ENTERED")).toBeVisible();
  await expect(page.getByText("13.2")).toHaveCount(0);

  const admin = await apiLogin(page, "admin@clinicopus.local", ADMIN_PASSWORD);
  const detail = await page.request.get(
    `${API}/api/v1/lab/items/${setup.itemId}/detail/`,
    { headers: headers(admin) }
  );
  expect(detail.ok(), await detail.text()).toBeTruthy();
  const observed = (await detail.json()) as { version_no: number };
  const released = await page.request.post(
    `${API}/api/v1/lab/items/${setup.itemId}/release/`,
    {
      headers: { ...headers(admin), "Idempotency-Key": `s30-clinician-release-${suffix}` },
      data: { expected_version: observed.version_no },
    }
  );
  expect(released.ok(), await released.text()).toBeTruthy();

  await page.getByRole("button", { name: "Refresh results", exact: true }).click();
  await expect(page.getByText("13.2")).toBeVisible();
  await expect(page.getByText("HIGH")).toBeVisible();
  await expect(page.getByText(/Released/).first()).toBeVisible();
  await expect(page.getByText(/Enter results/)).toHaveCount(0);

});

function s30P95(samples: number[]) {
  const sorted = [...samples].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1)];
}

test("S-30 200-item lab worklist paginates and records p95", async ({ page }) => {
  await login(page);
  const session = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const setup = await s30SetupLabItem(page, session, suffix, { action: "collect" });
  const nfrSession = await apiLogin(page, "demo", DEMO_PASSWORD);
  const services = (await (
    await page.request.get(`${API}/api/v1/billing/services/`, { headers: headers(nfrSession) })
  ).json()) as Array<{ id: string }>;
  const extraTestIds: string[] = [];
  for (let index = 0; index < 199; index += 1) {
    const created = await page.request.post(`${API}/api/v1/lab/tests/`, {
      headers: headers(nfrSession),
      data: {
        code: `NFR-${suffix}-${index}`,
        name: `Synthetic NFR test ${suffix}-${index}`,
        service_id: services[0].id,
        result_type: "NUMERIC",
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
    expect(created.ok(), await created.text()).toBeTruthy();
    extraTestIds.push(((await created.json()) as { id: string }).id);
  }
  const bulk = await page.request.post(`${API}/api/v1/lab/orders/`, {
    headers: { ...headers(nfrSession), "Idempotency-Key": `s30-nfr-bulk-${suffix}` },
    data: {
      encounter_id: setup.encounter.id,
      test_ids: extraTestIds,
      priority: "ROUTINE",
    },
  });
  expect(bulk.ok(), await bulk.text()).toBeTruthy();

  const apiSamples: number[] = [];
  for (let index = 0; index < 10; index += 1) {
    const started = Date.now();
    const response = await page.request.get(
      `${API}/api/v1/lab/worklist/?limit=50&offset=0`,
      { headers: headers(nfrSession) }
    );
    expect(response.ok(), await response.text()).toBeTruthy();
    apiSamples.push(Date.now() - started);
  }
  const worklistBody = (await (
    await page.request.get(`${API}/api/v1/lab/worklist/?limit=50&offset=0`, {
      headers: headers(nfrSession),
    })
  ).json()) as {
    pagination: { count: number; has_more: boolean };
    to_collect: unknown[];
    in_bench: unknown[];
    to_verify: unknown[];
    rejected: unknown[];
    released: unknown[];
    awaiting_payment: unknown[];
  };
  const pageRows =
    worklistBody.to_collect.length +
    worklistBody.in_bench.length +
    worklistBody.to_verify.length +
    worklistBody.rejected.length +
    worklistBody.released.length +
    worklistBody.awaiting_payment.length;
  expect(worklistBody.pagination.count).toBeGreaterThanOrEqual(200);
  expect(pageRows).toBe(50);
  expect(worklistBody.pagination.has_more).toBe(true);
  console.log(`S30_NFR_API_P95_MS=${s30P95(apiSamples)} samples=${apiSamples.join(",")}`);
  expect(s30P95(apiSamples)).toBeLessThanOrEqual(400);

  await page.goto("/lab");
  await expect(page.getByRole("listitem").first()).toBeVisible();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: Math.round((1.6 * 1024 * 1024) / 8),
    uploadThroughput: Math.round((750 * 1024) / 8),
    connectionType: "cellular3g",
  });
  const renderSamples: number[] = [];
  for (let index = 0; index < 5; index += 1) {
    await page.getByRole("link", { name: "Overview", exact: true }).click();
    const started = Date.now();
    await page.getByRole("link", { name: "Laboratory", exact: true }).click();
    await expect(page.getByRole("listitem").first()).toBeVisible();
    renderSamples.push(Date.now() - started);
  }
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
    connectionType: "none",
  });
  console.log(`S30_NFR_RENDER_P95_MS=${s30P95(renderSamples)} samples=${renderSamples.join(",")}`);
  expect(s30P95(renderSamples)).toBeLessThanOrEqual(2000);
});

test("S-35 Fix 1 review panel reconciles a result changed to draft", async ({ page }) => {
  await login(page);
  const demo = await apiLogin(page, "demo", DEMO_PASSWORD);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const setup = await s30SetupLabItem(page, demo, suffix, { action: "enter" });

  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await steadyFill(page, "Username", "admin@clinicopus.local");
  await steadyFill(page, "Password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();

  await page.goto("/lab");
  const row = page
    .getByRole("listitem")
    .filter({ hasText: `Synthetic S30 lab ${suffix}` })
    .first();
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Review and release", exact: true }).click();
  const releaseButton = page.getByRole("button", { name: "Verify & release", exact: true });
  await expect(releaseButton).toBeEnabled();

  const technician = await apiLogin(page, "demo", DEMO_PASSWORD);
  const values = setup.testBody.analytes.map((analyte, index) => ({
    analyte_id: analyte.id,
    value: index === 0 ? "12.5" : "6.0",
  }));
  const draft = await page.request.patch(
    `${API}/api/v1/lab/items/${setup.itemId}/results/`,
    {
      headers: { ...headers(technician), "Idempotency-Key": `s35-r1-browser-draft-${suffix}` },
      data: { values, complete: false },
    }
  );
  expect(draft.ok(), await draft.text()).toBeTruthy();
  const refreshed = await page.request.get(
    `${API}/api/v1/lab/items/${setup.itemId}/detail/`,
    { headers: headers(technician) }
  );
  expect(refreshed.ok(), await refreshed.text()).toBeTruthy();
  expect((await refreshed.json()).result_state).toBe("DRAFT");

  await page.getByRole("button", { name: "Refresh result", exact: true }).click();
  await expect(releaseButton).toHaveCount(0);
  await expect(page.getByText(/editable draft head/)).toBeVisible();
});
