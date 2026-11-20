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

function headers(session: { token: string; facilityId: string }) {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Facility-Id": session.facilityId,
    "Content-Type": "application/json",
  };
}

test("S-12 prescribes, signs, dispenses and charges one exact handover", async ({
  page,
}) => {
  await login(page);
  let session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const locations = (await (
    await page.request.get(`${API}/api/v1/inventory/locations/`, {
      headers: headers(session),
    })
  ).json()) as Array<{ id: string }>;
  expect(locations.length).toBeGreaterThan(0);
  const productResponse = await page.request.post(`${API}/api/v1/inventory/products/`, {
    headers: headers(session),
    data: {
      code: `S12-${suffix}`,
      generic_name: `Synthetic S12 medicine ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      strength: "500 mg",
      category: "MEDICINE",
    },
  });
  expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
  const product = (await productResponse.json()) as { id: string };
  const receipt = await page.request.post(`${API}/api/v1/inventory/receipts/`, {
    headers: { ...headers(session), "Idempotency-Key": `s12-grn-${suffix}` },
    data: {
      receipt_no: `GRN-S12-${suffix}`,
      lines: [
        {
          product_id: product.id,
          location_id: locations[0].id,
          batch_no: `B-S12-${suffix}`,
          expiry_date: new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10),
          quantity: "20.00",
          unit_cost: "100.00",
        },
      ],
    },
  });
  expect(receipt.ok(), await receipt.text()).toBeTruthy();
  const price = await page.request.post(`${API}/api/v1/inventory/prices/`, {
    headers: { ...headers(session), "Idempotency-Key": `s12-price-${suffix}` },
    data: {
      product_id: product.id,
      amount: "500.00",
      effective_from: new Date().toISOString().slice(0, 10),
    },
  });
  expect(price.ok(), await price.text()).toBeTruthy();

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S12",
      last_name: `Pharmacy${suffix}`,
      sex: "FEMALE",
      phone: `076${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok(), await patient.text()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const patientName = `S12 Pharmacy${suffix}`;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s12-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as {
    visit_id: string;
    queue_id: string;
    invoice_id: string;
  };
  expect(checkedIn.invoice_id).toBeTruthy();

  const triageWorklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=TRIAGE&state=WAITING,CALLED`,
    { headers: headers(session) }
  );
  const triageRows = (await triageWorklist.json()) as {
    entries: Array<{ id: string; visit_id: string | null; version: number }>;
  };
  const triageRow = triageRows.entries.find((row) => row.id === checkedIn.queue_id);
  expect(triageRow).toBeTruthy();
  const triage = await page.request.post(
    `${API}/api/v1/clinic/triage/${triageRow!.id}/`,
    {
      headers: {
        ...headers(session),
        "If-Match": `"${triageRow!.version}"`,
        "Idempotency-Key": `s12-triage-${suffix}`,
      },
      data: {
        expected_version: triageRow!.version,
        acuity: "ROUTINE",
        chief_complaint: "Synthetic S12 pharmacy complaint",
      },
    }
  );
  expect(triage.status(), await triage.text()).toBe(201);
  const consultationWorklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=WAITING`,
    { headers: headers(session) }
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
  const encounter = (await (await encounterPromise).json()) as { id: string };

  const reviewResponse = page.waitForResponse(
    (response) => response.url().endsWith("/allergies/review/") && response.status() === 200
  );
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", "Synthetic S12 no final diagnosis");
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
  await steadyFill(page, "Presenting complaint", "Synthetic S12 chest pain");

  // The UI sign-in rotates the browser session; refresh the API token before
  // the synthetic prescription command.
  session = await apiLogin(page);
  const draft = await page.request.patch(
    `${API}/api/v1/pharmacy/prescriptions/draft/`,
    {
      headers: { ...headers(session), "Idempotency-Key": `s12-draft-${suffix}` },
      data: {
        encounter_id: encounter.id,
        items: [
          {
            product_id: product.id,
            dose_amount: "1.00",
            dose_unit: "TABLET",
            route: "PO",
            frequency: "BD",
            duration_value: 5,
            duration_unit: "DAYS",
            quantity: "5.00",
            instructions: "Synthetic S12 instructions",
          },
        ],
      },
    }
  );
  expect(draft.ok(), await draft.text()).toBeTruthy();
  expect(((await draft.json()) as { status: string }).status).toBe("DRAFT");

  const savePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/encounters/${encounter.id}/notes/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await savePromise).status()).toBe(200);
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

  session = await apiLogin(page);
  const queue = (await (
    await page.request.get(`${API}/api/v1/pharmacy/queue/`, {
      headers: headers(session),
    })
  ).json()) as { active: Array<{ patient_name: string }> };
  expect(queue.active.some((row) => row.patient_name === patientName)).toBeTruthy();

  await page.goto("/pharmacy");
  await expect(page.getByRole("heading", { name: "Pharmacy" })).toBeVisible();
  const row = page
    .getByRole("listitem")
    .filter({ hasText: patientName })
    .filter({ hasText: "Synthetic S12 medicine" })
    .first();
  await expect(row).toBeVisible();
  const claimed = page.waitForResponse(
    (response) =>
      response.url().endsWith("/claim/") && response.request().method() === "POST"
  );
  await row.getByRole("button", { name: "Claim prescription", exact: true }).click();
  expect((await claimed).status()).toBe(201);

  const prepared = page.waitForResponse(
    (response) =>
      response.url().endsWith("/dispenses/") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Prepare dispense", exact: true }).click();
  const prepareResponse = await prepared;
  expect(prepareResponse.status()).toBe(201);
  const provisionalId = ((await prepareResponse.json()) as { id: string }).id;

  const review = page.getByRole("region", { name: "Dispense review" });
  await expect(review).toBeVisible();
  expect(
    await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[aria-label="Dispense review"]'))
    )
  ).toBeTruthy();
  await expect(review.getByText(/Synthetic S12 medicine/).first()).toBeVisible();
  await expect(review.getByText(/B-S12-/)).toBeVisible();
  await expect(review.getByText(/2500\.00/).first()).toBeVisible();
  await expect(review.getByRole("button", { name: "Confirm handover", exact: true })).toBeEnabled();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Pharmacy" })).toBeVisible();
  const resumedRow = page
    .getByRole("listitem")
    .filter({ hasText: patientName })
    .filter({ hasText: "Synthetic S12 medicine" })
    .first();
  await expect(
    resumedRow.getByRole("button", { name: "Resume preparation", exact: true })
  ).toBeVisible();
  await resumedRow.getByRole("button", { name: "Resume preparation", exact: true }).click();
  await expect(review).toBeVisible();
  await expect(review.getByText(/2500\.00/).first()).toBeVisible();

  const confirmAttempts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith(`/dispenses/${provisionalId}/confirm/`)
    ) {
      confirmAttempts.push(request.headers()["idempotency-key"] ?? "");
    }
  });
  let lostConfirm = false;
  await page.route(
    `**/api/v1/pharmacy/dispenses/${provisionalId}/confirm/`,
    async (route) => {
      if (!lostConfirm) {
        lostConfirm = true;
        await route.fetch();
        await route.abort("failed");
        return;
      }
      await route.continue();
    }
  );
  await review.getByRole("button", { name: "Confirm handover", exact: true }).click();
  await expect(page.getByText(/pharmacy outcome is uncertain/i)).toBeVisible();
  await page.getByRole("button", { name: "Retry uncertain pharmacy step", exact: true }).click();
  await expect(
    page.getByText(`${patientName} · dispense confirmed`)
  ).toBeVisible();
  expect(confirmAttempts).toHaveLength(2);
  expect(confirmAttempts[1]).toBe(confirmAttempts[0]);

  session = await apiLogin(page);
  const invoice = await page.request.get(
    `${API}/api/v1/billing/invoices/${checkedIn.invoice_id}/`,
    { headers: headers(session) }
  );
  expect(invoice.ok(), await invoice.text()).toBeTruthy();
  const invoiceBody = (await invoice.json()) as {
    total: string;
    items: Array<{ source_type: string | null; amount: string }>;
  };
  expect(invoiceBody.total).toBe("32500.00");
  const dispenseLines = invoiceBody.items.filter(
    (item) => item.source_type === "DISPENSE_LINE"
  );
  expect(dispenseLines).toHaveLength(1);
  expect(dispenseLines[0].amount).toBe("2500.00");

  const movements = await page.request.get(
    `${API}/api/v1/inventory/movements/?movement_type=OUT_DISPENSE`,
    { headers: headers(session) }
  );
  const movementBody = (await movements.json()) as Array<{
    movement_type: string;
  }>;
  expect(movementBody.some((item) => item.movement_type === "OUT_DISPENSE")).toBeTruthy();
});

test("S-29-R6 lost prepare response resumes the original provisional identity", async ({
  page,
}) => {
  await login(page);
  let session = await apiLogin(page);
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);

  const locations = (await (
    await page.request.get(`${API}/api/v1/inventory/locations/`, { headers: headers(session) })
  ).json()) as Array<{ id: string }>;
  const productResponse = await page.request.post(`${API}/api/v1/inventory/products/`, {
    headers: headers(session),
    data: {
      code: `S29R6-${suffix}`,
      generic_name: `Synthetic S29 R6 medicine ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      strength: "500 mg",
      category: "MEDICINE",
    },
  });
  expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
  const product = (await productResponse.json()) as { id: string };
  const receipt = await page.request.post(`${API}/api/v1/inventory/receipts/`, {
    headers: { ...headers(session), "Idempotency-Key": `s29-r6-grn-${suffix}` },
    data: {
      receipt_no: `GRN-S29R6-${suffix}`,
      lines: [
        {
          product_id: product.id,
          location_id: locations[0].id,
          batch_no: `B-S29R6-${suffix}`,
          expiry_date: new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10),
          quantity: "20.00",
          unit_cost: "100.00",
        },
      ],
    },
  });
  expect(receipt.ok(), await receipt.text()).toBeTruthy();
  const price = await page.request.post(`${API}/api/v1/inventory/prices/`, {
    headers: { ...headers(session), "Idempotency-Key": `s29-r6-price-${suffix}` },
    data: {
      product_id: product.id,
      amount: "500.00",
      effective_from: new Date().toISOString().slice(0, 10),
    },
  });
  expect(price.ok(), await price.text()).toBeTruthy();

  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: headers(session),
    data: {
      first_name: "S29R6",
      last_name: `Pharmacy${suffix}`,
      sex: "FEMALE",
      phone: `076${suffix.slice(-6).padStart(6, "0")}`,
    },
  });
  expect(patient.ok(), await patient.text()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;
  const patientName = `S29R6 Pharmacy${suffix}`;
  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...headers(session), "Idempotency-Key": `s29-r6-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok(), await checkIn.text()).toBeTruthy();
  const checkedIn = (await checkIn.json()) as { visit_id: string; queue_id: string };

  const triageWorklist = await page.request.get(
    `${API}/api/v1/clinic/queue/operational/?queue_type=TRIAGE&state=WAITING,CALLED`,
    { headers: headers(session) }
  );
  const triageRows = (await triageWorklist.json()) as {
    entries: Array<{ id: string; version: number }>;
  };
  const triageRow = triageRows.entries.find((row) => row.id === checkedIn.queue_id);
  expect(triageRow).toBeTruthy();
  const triage = await page.request.post(
    `${API}/api/v1/clinic/triage/${triageRow!.id}/`,
    {
      headers: {
        ...headers(session),
        "If-Match": `"${triageRow!.version}"`,
        "Idempotency-Key": `s29-r6-triage-${suffix}`,
      },
      data: {
        expected_version: triageRow!.version,
        acuity: "ROUTINE",
        chief_complaint: "Synthetic S29 R6 complaint",
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

  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", "Synthetic S29 R6 no final diagnosis");
  await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
  await expect(page.getByTestId("no-diagnosis-state")).toBeVisible();
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", "Synthetic S29 R6 chest pain");

  session = await apiLogin(page);
  const draft = await page.request.patch(
    `${API}/api/v1/pharmacy/prescriptions/draft/`,
    {
      headers: { ...headers(session), "Idempotency-Key": `s29-r6-draft-${suffix}` },
      data: {
        encounter_id: encounter.id,
        items: [
          {
            product_id: product.id,
            dose_amount: "1.00",
            dose_unit: "TABLET",
            route: "PO",
            frequency: "BD",
            duration_value: 5,
            duration_unit: "DAYS",
            quantity: "5.00",
            instructions: "Synthetic S29 R6 instructions",
          },
        ],
      },
    }
  );
  expect(draft.ok(), await draft.text()).toBeTruthy();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const savePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/encounters/${encounter.id}/notes/`) &&
      response.request().method() === "PATCH"
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await savePromise).status()).toBe(200);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();

  const signPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/encounters/${encounter.id}/sign/`) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  expect((await signPromise).status()).toBe(200);

  await page.goto("/pharmacy");
  const row = page
    .getByRole("listitem")
    .filter({ hasText: patientName })
    .filter({ hasText: `Synthetic S29 R6 medicine ${suffix}` })
    .first();
  await expect(row).toBeVisible();

  const prepareAttempts: Array<{ key: string | undefined; body: string | null }> = [];
  const confirmUrls: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "POST") return;
    if (/\/api\/v1\/pharmacy\/prescriptions\/[^/]+\/dispenses\/$/.test(request.url())) {
      prepareAttempts.push({
        key: request.headers()["idempotency-key"],
        body: request.postData(),
      });
    }
    if (request.url().endsWith("/confirm/")) confirmUrls.push(request.url());
  });
  let lostPrepare = false;
  await page.route(
    /\/api\/v1\/pharmacy\/prescriptions\/[^/]+\/dispenses\/$/,
    async (route) => {
      if (!lostPrepare) {
        lostPrepare = true;
        await route.fetch();
        await route.abort("failed");
        return;
      }
      await route.continue();
    }
  );

  await row.getByRole("button", { name: "Claim prescription", exact: true }).click();
  await page.getByRole("button", { name: "Prepare dispense", exact: true }).click();
  await expect(page.getByText(/pharmacy outcome is uncertain/i)).toBeVisible();
  await page.getByRole("button", { name: "Retry uncertain pharmacy step", exact: true }).click();
  await expect(page.getByRole("region", { name: "Dispense review" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm handover", exact: true }).click();
  await expect(page.getByText(`${patientName} · dispense confirmed`)).toBeVisible();

  expect(prepareAttempts).toHaveLength(2);
  expect(prepareAttempts[1].key).toBe(prepareAttempts[0].key);
  expect(prepareAttempts[1].body).toBe(prepareAttempts[0].body);
  expect(prepareAttempts[0].key).toBeTruthy();
  expect(confirmUrls).toHaveLength(1);
  const provisionalId = confirmUrls[0].match(/\/dispenses\/([0-9a-f-]+)\/confirm\//)?.[1];
  expect(provisionalId).toBeTruthy();
  session = await apiLogin(page);
  const queueResponse = await page.request.get(`${API}/api/v1/pharmacy/queue/`, {
    headers: headers(session),
  });
  expect(queueResponse.ok(), await queueResponse.text()).toBeTruthy();
  const queue = (await queueResponse.json()) as {
    counselling: Array<{ patient_name: string; dispense_id: string }>;
  };
  const counselling = queue.counselling.filter((item) => item.patient_name === patientName);
  expect(counselling).toHaveLength(1);
  expect(counselling[0].dispense_id).toBe(provisionalId);
});
