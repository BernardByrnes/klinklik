import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}

const STATUS_ENDPOINT = "**/api/v1/clinic/patients/*/allergy-status/";
const ADD_ENDPOINT = "**/api/v1/clinic/patients/*/allergies/";
const REVIEW_ENDPOINT = "**/api/v1/clinic/encounters/*/allergies/review/";
const SIGN_ENDPOINT = "**/api/v1/clinic/encounters/*/sign/";
const SYNTHETIC_TRIAGE = "Phase 1M-B verification — synthetic triage complaint";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt++) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(100);
  }
  throw new Error("Input did not hold its value: " + label);
}

async function login(page: Page) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", DEMO_PASSWORD as string);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);
}

async function registerAndCheckIn(page: Page, firstName: string, phone: string) {
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/\/patients$/);
  await steadyFill(page, "First name", firstName);
  await steadyFill(page, "Last name", "Synthetic");
  await steadyFill(page, "Phone", phone);
  await page.locator("form").getByRole("button", { name: "Register patient" }).click();
  const patientName = firstName + " Synthetic";
  await expect(page.getByText(new RegExp(patientName + " registered as P-"))).toBeVisible();
  await page.getByRole("button", { name: "Check in patient" }).click();
  await expect(page.getByText(new RegExp(patientName + " checked in as"))).toBeVisible();
  return patientName;
}

async function triage(page: Page, patientName: string) {
  await page.locator('nav a[href="/queue"]').click();
  await expect(page).toHaveURL(/\/queue$/);
  await page.getByLabel("Filter queue").fill(patientName);
  const row = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Claim" }).click();
  await expect(row.getByText("Called")).toBeVisible();
  await row.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/triage/);
  await steadyFill(page, "Chief complaint", SYNTHETIC_TRIAGE);
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText(new RegExp("Triage recorded for " + patientName))).toBeVisible();
}

async function createConsultation(page: Page, prefix: string) {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, prefix + suffix, "078" + suffix);
  await triage(page, patientName);
  await openEncounter(page, patientName);
  return patientName;
}

async function openEncounter(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByTestId("allergy-banner")).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
}

async function chooseNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  const statusRequest = page.waitForRequest((request) => request.url().endsWith("/allergy-status/") && request.method() === "POST");
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  const request = await statusRequest;
  expect(request.headers()["if-match"]).toBeTruthy();
  await statusResponse;
  await expect(page.getByTestId("allergy-banner")).toContainText("No known allergies");
  await expect(page.getByTestId("allergy-banner")).toContainText("Allergy status not yet reviewed for this encounter.");
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  const reviewRequest = page.waitForRequest((request) => request.url().endsWith("/allergies/review/") && request.method() === "POST");
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  const review = await reviewRequest;
  expect(review.headers()["if-match"]).toBeTruthy();
  await reviewResponse;
  await expect(page.getByTestId("allergy-banner")).toContainText("Reviewed for this encounter");
}

async function addAllergy(page: Page, substance: string, reaction: string, severity = "MODERATE") {
  await page.getByRole("button", { name: "Add allergy", exact: true }).click();
  await steadyFill(page, "Substance", substance);
  await steadyFill(page, "Reaction (optional)", reaction);
  await page.getByLabel("Severity", { exact: true }).selectOption(severity);
  const requestPromise = page.waitForRequest((request) => request.url().endsWith("/allergies/") && request.method() === "POST");
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/allergies/") && response.status() === 201);
  await page.getByRole("button", { name: "Save allergy", exact: true }).click();
  const request = await requestPromise;
  expect(JSON.parse(request.postData() ?? "{}")).toEqual({ substance, reaction, severity });
  await responsePromise;
}

async function addComplaint(page: Page, value = "Phase 1M-B verification — synthetic presenting complaint") {
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", value);
}

async function signAfterReview(page: Page) {
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
  await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
  await responsePromise;
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
}

test.describe("Phase 1M-B clinician allergy banner and review workflow", () => {
  test("shows NOT_RECORDED and blocks signing locally without a sign request", async ({ page }) => {
    await createConsultation(page, "Phase1MB-NotRecorded-");
    await expect(page.getByTestId("allergy-banner")).toContainText("Allergies: Not recorded");
    let signRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/sign/") && request.method() === "POST") signRequests += 1;
    });
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Record the patient's allergy status before signing." })).toBeVisible();
    expect(signRequests).toBe(0);
  });

  test("records NKA with If-Match and requires a separate review", async ({ page }) => {
    await createConsultation(page, "Phase1MB-NKA-");
    await chooseNkaAndReview(page);
  });

  test("records UNKNOWN as an explicit state and keeps review required", async ({ page }) => {
    await createConsultation(page, "Phase1MB-Unknown-");
    const requestPromise = page.waitForRequest((request) => request.url().endsWith("/allergy-status/") && request.method() === "POST");
    await page.getByRole("button", { name: "Unknown", exact: true }).click();
    const request = await requestPromise;
    expect(JSON.parse(request.postData() ?? "{}")).toEqual({ status: "UNKNOWN" });
    expect(request.headers()["if-match"]).toBeTruthy();
    await expect(page.getByTestId("allergy-banner")).toContainText("Allergy status: Unknown");
    await expect(page.getByTestId("allergy-banner")).toContainText("Allergy status not yet reviewed for this encounter.");
  });

  test("adds multiple active allergies and never offers NKA or UNKNOWN over them", async ({ page }) => {
    await createConsultation(page, "Phase1MB-Multiple-");
    await addAllergy(page, "Phase 1M-B synthetic Penicillin", "Phase 1M-B synthetic rash");
    await addAllergy(page, "Phase 1M-B synthetic Latex", "Phase 1M-B synthetic wheeze", "SEVERE");
    const banner = page.getByTestId("allergy-banner");
    await expect(banner).toContainText("Phase 1M-B synthetic Penicillin");
    await expect(banner).toContainText("Reaction: Phase 1M-B synthetic rash");
    await expect(banner).toContainText("Severity: Moderate");
    await expect(banner).toContainText("Phase 1M-B synthetic Latex");
    await expect(page.getByRole("button", { name: "No known allergies", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Unknown", exact: true })).toHaveCount(0);
  });

  test("requires a reason for entered-in-error and transitions the last active allergy to NOT_RECORDED", async ({ page }) => {
    await createConsultation(page, "Phase1MB-EnteredError-");
    await addAllergy(page, "Phase 1M-B synthetic entered-in-error", "Phase 1M-B synthetic reaction");
    await page.getByRole("button", { name: "Mark entered in error", exact: true }).click();
    await page.getByRole("button", { name: "Confirm entered in error", exact: true }).click();
    await expect(page.getByText("Enter a reason before confirming.", { exact: true })).toBeVisible();
    await steadyFill(page, "Reason for entering in error", "Phase 1M-B synthetic correction reason");
    const requestPromise = page.waitForRequest((request) => request.url().includes("/entered-in-error/") && request.method() === "POST");
    await page.getByRole("button", { name: "Confirm entered in error", exact: true }).click();
    const request = await requestPromise;
    expect(request.headers()["if-match"]).toBeTruthy();
    await expect(page.getByTestId("allergy-banner")).toContainText("Allergies: Not recorded");
    await expect(page.getByTestId("allergy-banner")).not.toContainText("Phase 1M-B synthetic entered-in-error");
  });

  test("stales an encounter review after an allergy change and blocks signing until review repeats", async ({ page }) => {
    await createConsultation(page, "Phase1MB-Stale-");
    await chooseNkaAndReview(page);
    await addAllergy(page, "Phase 1M-B synthetic stale allergy", "Phase 1M-B synthetic stale reaction");
    const banner = page.getByTestId("allergy-banner");
    await expect(banner).toContainText("Allergy information changed — review again before signing.");
    await addComplaint(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Review the current allergy status before signing." })).toBeVisible();
  });

  test("signs successfully only after a current allergy review", async ({ page }) => {
    await createConsultation(page, "Phase1MB-Sign-");
    await chooseNkaAndReview(page);
    await addComplaint(page);
    await signAfterReview(page);
    const banner = page.getByTestId("allergy-banner");
    await expect(banner).toBeVisible();
    await expect(banner.getByRole("button")).toHaveCount(0);
  });

  test("maps a server allergy review prerequisite failure without exposing the internal code", async ({ page }) => {
    await createConsultation(page, "Phase1MB-ServerFallback-");
    await chooseNkaAndReview(page);
    await addComplaint(page);
    await page.route(SIGN_ENDPOINT, async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ code: "ALLERGY_REVIEW_STALE", detail: "Synthetic server state changed." }),
      });
    });
    try {
      await page.getByRole("tab", { name: "Notes", exact: true }).click();
      await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
      await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Review the current allergy status before signing." })).toBeVisible();
      await expect(page.getByText("ALLERGY_REVIEW_STALE", { exact: true })).toHaveCount(0);
    } finally {
      await page.unroute(SIGN_ENDPOINT);
    }
  });

  test("adopts the authoritative state after a 412 without replaying the stale mutation", async ({ page }) => {
    await createConsultation(page, "Phase1MB-412-");
    let requestCount = 0;
    await page.route(STATUS_ENDPOINT, async (route) => {
      requestCount += 1;
      await route.fulfill({
        status: 412,
        contentType: "application/json",
        body: JSON.stringify({
          code: "ALLERGY_STATE_REVISION_CONFLICT",
          detail: "Synthetic stale allergy state.",
          allergy_status: "UNKNOWN",
          active_allergies: [],
          allergy_revision: 3,
          allergy_state_etag: "synthetic-authoritative-etag",
        }),
      });
    });
    try {
      await page.getByRole("button", { name: "No known allergies", exact: true }).click();
      await expect(page.getByTestId("allergy-banner")).toContainText("Allergy status: Unknown");
      await expect(page.getByTestId("allergy-banner")).toContainText("Allergy information changed. Review the latest record before trying again.");
      expect(requestCount).toBe(1);
    } finally {
      await page.unroute(STATUS_ENDPOINT);
    }
  });

  test("does not let a delayed Patient A allergy response affect Patient B", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1MB-RaceA-" + suffix, "075" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1MB-RaceB-" + suffix, "076" + suffix);
    await triage(page, patientA);
    await triage(page, patientB);
    await openEncounter(page, patientA);
    let release: (() => void) | null = null;
    const delayed = new Promise<void>((resolve) => { release = resolve; });
    await page.route(STATUS_ENDPOINT, async (route) => {
      await delayed;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          allergy_status: "NKA",
          active_allergies: [],
          allergy_revision: 1,
          allergy_state_etag: "synthetic-late-etag",
        }),
      });
    });
    try {
      await page.getByRole("button", { name: "No known allergies", exact: true }).click();
      await page.getByRole("listitem").filter({ hasText: patientB }).click();
      await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
      release?.();
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await page.getByRole("button", { name: "Start encounter" }).click();
      await expect(page.getByTestId("allergy-banner")).toContainText("Allergies: Not recorded");
      await expect(page.getByTestId("allergy-banner").getByRole("heading", { name: "No known allergies", exact: true })).toHaveCount(0);
    } finally {
      release?.();
      await page.unroute(STATUS_ENDPOINT);
    }
  });

  test("keeps the banner read-only after signing and introduces no browser allergy persistence or drug-check copy", async ({ page }) => {
    await createConsultation(page, "Phase1MB-Safety-");
    await chooseNkaAndReview(page);
    await addComplaint(page);
    await signAfterReview(page);
    const result = await page.evaluate(async () => ({
      localStorageKeys: Object.keys(localStorage),
      sessionStorageKeys: Object.keys(sessionStorage),
      indexedDbAvailable: "indexedDB" in window,
      serviceWorkerRegistrations: "serviceWorker" in navigator ? (await navigator.serviceWorker.getRegistrations()).length : 0,
    }));
    expect(result.localStorageKeys.some((key) => /allergy|draft/i.test(key))).toBe(false);
    expect(result.sessionStorageKeys.some((key) => /allergy|draft/i.test(key))).toBe(false);
    expect(result.serviceWorkerRegistrations).toBe(0);
    const bannerText = (await page.getByTestId("allergy-banner").innerText()).toLowerCase();
    expect(bannerText).not.toMatch(/interaction|contraindication|match.*medicine|medicine.*match/);
    await expect(page.getByRole("button", { name: "Add allergy", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Review allergies", exact: true })).toHaveCount(0);
  });

  test("warns before switching away from an open unsent allergy form and discards it only after confirmation", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1MB-FormA-" + suffix, "073" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1MB-FormB-" + suffix, "074" + suffix);
    await triage(page, patientA);
    await triage(page, patientB);
    await openEncounter(page, patientA);
    await page.getByRole("button", { name: "Add allergy", exact: true }).click();
    await steadyFill(page, "Substance", "Phase 1M-B unsent Patient A allergy");
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientA, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Substance", { exact: true })).toHaveValue("Phase 1M-B unsent Patient A allergy");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await page.getByRole("button", { name: "Start encounter" }).click();
    await expect(page.getByTestId("allergy-banner")).toContainText("Allergies: Not recorded");
    await expect(page.getByLabel("Substance", { exact: true })).toHaveCount(0);
  });
});
