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
  await page.getByLabel("Priority", { exact: true }).selectOption("URGENT");
  const triagePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/clinic/triage/${triageQueueId}/`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Complete triage" }).click();
  const triageResponse = await triagePromise;
  expect(triageResponse.status()).toBe(201);
  const triageBody = (await triageResponse.json()) as { queue_entry: { state: string } };
  expect(triageBody.queue_entry.state).toBe("COMPLETED");
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
