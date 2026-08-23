import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}
const NOTE_PATCH = "**/api/v1/clinic/encounters/*/notes/";
const SYNTHETIC_TRIAGE = "Phase 1L-B verification — synthetic triage complaint";

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
  await steadyFill(page, "Password", DEMO_PASSWORD);
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

async function triageFromQueue(page: Page, patientName: string) {
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

async function openHistory(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByTestId("presenting-complaints-editor")).toBeVisible();
}

async function recordNoFinalDiagnosis(page: Page) {
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", "Phase 1N-B compatibility synthetic no final diagnosis");
  await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
  await expect(page.getByTestId("no-diagnosis-state")).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
}

async function createConsultation(page: Page, prefix: string) {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, prefix + suffix, "078" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await recordNoFinalDiagnosis(page);
  return patientName;
}

async function setNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await statusResponse;
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
}

function isNotePatch(request: { url(): string; method(): string }) {
  return request.url().includes("/api/v1/clinic/encounters/") && request.url().endsWith("/notes/") && request.method() === "PATCH";
}

test.describe("Phase 1L-B structured presenting complaints", () => {
  test("renders ordered rows, preserves text and duration, reorders, and survives section switching", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Editor-");
    const first = page.getByLabel("Presenting complaint", { exact: true });
    await expect(first).toHaveValue("");
    await steadyFill(page, "Presenting complaint", "  Phase 1L-B synthetic cough  ");
    await page.getByLabel("Duration value for presenting complaint 1").fill("2");
    await page.getByLabel("Duration unit for presenting complaint 1").selectOption("DAYS");
    await page.getByRole("button", { name: "Add complaint" }).click();
    await steadyFill(page, "Presenting complaint 2", "Phase 1L-B synthetic fever");
    await expect(page.getByRole("button", { name: "Move presenting complaint 1 up" })).toBeDisabled();
    await page.getByRole("button", { name: "Move presenting complaint 2 up" }).click();
    const saveRequest = page.waitForRequest((request) => isNotePatch(request));
    await page.getByRole("button", { name: "Save draft" }).click();
    const request = await saveRequest;
    const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown; complaints?: unknown };
    expect(body.content).toEqual({});
    expect(body.complaints).toEqual([
      { text: "Phase 1L-B synthetic fever", duration_value: null, duration_unit: null },
      { text: "  Phase 1L-B synthetic cough  ", duration_value: 2, duration_unit: "DAYS" },
    ]);
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic fever");
    await expect(page.getByLabel("Presenting complaint 2", { exact: true })).toHaveValue("  Phase 1L-B synthetic cough  ");
  });

  test("keeps blank, paired-duration, and overlength rows in memory without invalid requests", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Validation-");
    let patchCount = 0;
    page.on("request", (request) => {
      if (isNotePatch(request)) patchCount += 1;
    });
    await steadyFill(page, "Presenting complaint", "   ");
    await page.waitForTimeout(3500);
    expect(patchCount).toBe(0);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByTestId("presenting-complaint-row-0").getByRole("alert").filter({ hasText: "Enter a presenting complaint" })).toBeVisible();
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic duration validation");
    await page.getByLabel("Duration value for presenting complaint 1").fill("-1");
    await page.getByLabel("Duration unit for presenting complaint 1").selectOption("DAYS");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByTestId("presenting-complaint-row-0").getByRole("alert").filter({ hasText: "positive" })).toBeVisible();
    expect(patchCount).toBe(0);
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveAttribute("maxlength", "500");
  });

  test("keeps triage separate and only copies it after an explicit action", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Triage-");
    await expect(page.getByTestId("triage-complaint")).toHaveText(SYNTHETIC_TRIAGE);
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("");
    await page.getByRole("button", { name: "Copy from triage" }).click();
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue(SYNTHETIC_TRIAGE);
    await page.getByRole("button", { name: "Add complaint" }).click();
    await page.getByRole("button", { name: "Copy from triage" }).click();
    await expect(page.getByLabel("Presenting complaint 2", { exact: true })).toHaveValue("");
    await expect(page.getByLabel("Presenting complaint 3", { exact: true })).toHaveValue(SYNTHETIC_TRIAGE);
  });

  test("autosaves complaint-only changes with an empty content object and If-Match marker", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Autosave-");
    const requestPromise = page.waitForRequest((request) => isNotePatch(request));
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic autosave complaint");
    const request = await requestPromise;
    const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown; complaints?: unknown };
    expect(body.content).toEqual({});
    expect(body.complaints).toEqual([{ text: "Phase 1L-B synthetic autosave complaint", duration_value: null, duration_unit: null }]);
    expect(request.headers()["if-match"]).toBeTruthy();
    expect(request.headers()["x-klinklik-autosave"]).toBe("1");
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  });

  test("manual Save explicitly clears a structured complaint without writing legacy content", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Clear-");
    const firstSave = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.request().method() === "PATCH" && response.status() === 200);
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic clear target");
    await firstSave;
    await page.getByRole("button", { name: "Remove presenting complaint 1" }).click();
    const requestPromise = page.waitForRequest((request) => isNotePatch(request));
    await page.getByRole("button", { name: "Save draft" }).click();
    const request = await requestPromise;
    const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown; complaints?: unknown };
    expect(body.content).toEqual({});
    expect(body.complaints).toEqual([]);
    expect(request.headers()["x-klinklik-autosave"]).toBeUndefined();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  });

  test("retries a transient complaint save once with current dirty rows and bounded single-loop state", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Retry-");
    const requests: Array<{ body: Record<string, unknown>; inFlight: number }> = [];
    let inFlight = 0;
    let maxInFlight = 0;
    let failFirst = true;
    page.on("request", (request) => {
      if (!isNotePatch(request)) return;
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      requests.push({ body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>, inFlight });
    });
    page.on("response", (response) => {
      if (response.url().endsWith("/notes/") && response.request().method() === "PATCH") inFlight = Math.max(0, inFlight - 1);
    });
    await page.route(NOTE_PATCH, async (route) => {
      if (route.request().method() === "PATCH" && failFirst) {
        failFirst = false;
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic transient failure" }) });
        return;
      }
      await route.continue();
    });
    try {
      const firstFailure = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 503);
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic first retry value");
      await firstFailure;
      await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
      await page.evaluate(() => window.dispatchEvent(new Event("offline")));
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic current retry value");
      await page.getByRole("button", { name: "Add complaint" }).click();
      await steadyFill(page, "Presenting complaint 2", "Phase 1L-B synthetic current second complaint");
      const retry = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 200);
      await page.evaluate(() => window.dispatchEvent(new Event("online")));
      await retry;
      expect(requests).toHaveLength(2);
      expect((requests[0].body.complaints as unknown[])[0]).toEqual({ text: "Phase 1L-B synthetic first retry value", duration_value: null, duration_unit: null });
      expect(requests[1].body.complaints).toEqual([
        { text: "Phase 1L-B synthetic current retry value", duration_value: null, duration_unit: null },
        { text: "Phase 1L-B synthetic current second complaint", duration_value: null, duration_unit: null },
      ]);
      expect(maxInFlight).toBe(1);
      expect(requests[0].body.content).toEqual({});
      expect(requests[1].body.content).toEqual({});
      await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("manual Save cancels a pending complaint retry timer", async ({ page }) => {
    await createConsultation(page, "Phase1LB-ManualRetry-");
    let failFirst = true;
    const markers: string[] = [];
    page.on("request", (request) => {
      if (isNotePatch(request)) markers.push(request.headers()["x-klinklik-autosave"] ?? "manual");
    });
    await page.route(NOTE_PATCH, async (route) => {
      if (route.request().method() === "PATCH" && failFirst) {
        failFirst = false;
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic transient failure" }) });
        return;
      }
      await route.continue();
    });
    try {
      const failure = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 503);
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic manual retry complaint");
      await failure;
      await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
      const manualSave = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 200);
      await page.getByRole("button", { name: "Save draft" }).click();
      await manualSave;
      await page.waitForTimeout(2500);
      expect(markers).toEqual(["1", "manual"]);
      await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("does not hammer while offline, retries online, and protects complaint-only unload", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Offline-");
    let patchCount = 0;
    page.on("request", (request) => {
      if (isNotePatch(request)) patchCount += 1;
    });
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic offline complaint");
    await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
    await page.waitForTimeout(3500);
    expect(patchCount).toBe(0);
    const blocked = await page.evaluate(() => { const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented; });
    expect(blocked).toBe(true);
    const retry = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 200);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await retry;
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    const clean = await page.evaluate(() => { const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented; });
    expect(clean).toBe(false);
  });

  test("reconciles a lost complaint response without a false structured conflict", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Lost-");
    let firstRequest = true;
    await page.route(NOTE_PATCH, async (route) => {
      if (route.request().method() === "PATCH" && firstRequest) {
        firstRequest = false;
        await route.fetch();
        await route.abort("failed");
        return;
      }
      await route.continue();
    });
    try {
      const requests: Array<{ body: Record<string, unknown>; etag: string | undefined }> = [];
      page.on("request", (request) => { if (isNotePatch(request)) requests.push({ body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>, etag: request.headers()["if-match"] }); });
      const first = page.waitForRequest((request) => isNotePatch(request));
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic lost response complaint");
      await first;
      await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
      const reconciliation = page.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 412);
      await reconciliation;
      expect(requests).toHaveLength(2);
      expect(requests[1].body.complaints).toEqual(requests[0].body.complaints);
      expect(requests[1].etag).toBe(requests[0].etag);
      await expect(page.getByTestId("complaint-conflict")).toHaveCount(0);
      await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("blocks automatic retry after a true same-complaint conflict and preserves both versions", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1LB-Conflict-");
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic conflict baseline");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    const stalePage = await page.context().newPage();
    try {
      await stalePage.goto("/consultations");
      await openHistory(stalePage, patientName);
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic server value");
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(page.getByText("Consultation draft saved.")).toBeVisible();
      await steadyFill(stalePage, "Presenting complaint", "Phase 1L-B synthetic local conflict value");
      let staleConflictResponses = 0;
      stalePage.on("response", (response) => {
        if (isNotePatch(response.request()) && [409, 412].includes(response.status())) staleConflictResponses += 1;
      });
      const conflict = stalePage.waitForResponse((response) => response.url().endsWith("/notes/") && [409, 412].includes(response.status()));
      await stalePage.getByRole("button", { name: "Save draft" }).click();
      await conflict;
      await stalePage.getByRole("tab", { name: "History", exact: true }).click();
      await expect(stalePage.getByTestId("complaint-conflict")).toBeVisible();
      await expect(stalePage.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic local conflict value");
      await expect(stalePage.getByTestId("complaint-conflict")).toContainText("Phase 1L-B synthetic server value");
      await stalePage.waitForTimeout(2500);
      expect(staleConflictResponses).toBe(1);
    } finally {
      await stalePage.close();
    }
  });

  test("rebases a non-overlapping HPI change while retrying a dirty complaint", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1LB-Rebase-");
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic rebase baseline");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    const stalePage = await page.context().newPage();
    try {
      await stalePage.goto("/consultations");

      await openHistory(stalePage, patientName);
      await steadyFill(page, "History of present illness (HPI)", "Phase 1L-B synthetic server HPI");
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(page.getByText("Consultation draft saved.")).toBeVisible();
      await steadyFill(stalePage, "Presenting complaint", "Phase 1L-B synthetic local rebase complaint");
      const resolution = stalePage.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 200);
      await stalePage.getByRole("button", { name: "Save draft" }).click();
      await resolution;
      await expect(stalePage.getByLabel("History of present illness (HPI)")).toHaveValue("Phase 1L-B synthetic server HPI");
      await expect(stalePage.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic local rebase complaint");
    } finally {
      await stalePage.close();
    }
  });

  test("rebases a non-overlapping dirty HPI after the server complaint list changes", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1LB-RebaseReverse-");
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic reverse baseline");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    const stalePage = await page.context().newPage();
    try {
      await stalePage.goto("/consultations");

      await openHistory(stalePage, patientName);
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic server complaint");
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(page.getByText("Consultation draft saved.")).toBeVisible();
      await steadyFill(stalePage, "History of present illness (HPI)", "Phase 1L-B synthetic local HPI");
      const resolution = stalePage.waitForResponse((response) => response.url().endsWith("/notes/") && response.status() === 200);
      await stalePage.getByRole("button", { name: "Save draft" }).click();
      await resolution;
      await expect(stalePage.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic server complaint");
      await expect(stalePage.getByLabel("History of present illness (HPI)")).toHaveValue("Phase 1L-B synthetic local HPI");
    } finally {
      await stalePage.close();
    }
  });

  test("preserves a complaint edited after a response is in flight and sends it on the next save", async ({ page }) => {
    await createConsultation(page, "Phase1LB-InFlight-");
    let firstRequest = true;
    let releaseResponse: (() => void) | null = null;
    const responsePaused = new Promise<void>((resolve) => { releaseResponse = resolve; });
    await page.route(NOTE_PATCH, async (route) => {
      if (route.request().method() === "PATCH" && firstRequest) {
        firstRequest = false;
        const response = await route.fetch();
        await responsePaused;
        await route.fulfill({ response });
        return;
      }
      await route.continue();
    });
    try {
      const firstRequestSeen = page.waitForRequest((request) => isNotePatch(request));
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic in-flight first value");
      await firstRequestSeen;
      await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic in-flight current value");
      releaseResponse?.();
      await expect(page.getByText("Consultation draft saved; newer edits remain unsaved.")).toBeVisible();
      const secondRequest = page.waitForRequest((request) => isNotePatch(request));
      const request = await secondRequest;
      const body = JSON.parse(request.postData() ?? "{}") as { complaints?: unknown };
      expect(body.complaints).toEqual([{ text: "Phase 1L-B synthetic in-flight current value", duration_value: null, duration_unit: null }]);
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("blocks empty sign locally, includes valid dirty complaints on sign, and shows signed order read-only", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Sign-");
    await setNkaAndReview(page);
    let signRequests = 0;
    page.on("request", (request) => { if (request.url().endsWith("/sign/") && request.method() === "POST") signRequests += 1; });
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation" }).click();
    await page.getByRole("button", { name: "Confirm signature" }).click();
    await expect(page.getByRole("tab", { name: "History", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(/Add at least one valid presenting complaint/)).toBeVisible();
    expect(signRequests).toBe(0);
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic signed complaint");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    const signResponse = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
    await page.getByRole("button", { name: "Sign consultation" }).click();
    await page.getByRole("button", { name: "Confirm signature" }).click();
    const response = await signResponse;
    const body = await response.json() as { complaints?: unknown };
    expect(body.complaints).toEqual([{ text: "Phase 1L-B synthetic signed complaint", duration_value: null, duration_unit: null }]);
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByTestId("signed-presenting-complaints")).toContainText("Phase 1L-B synthetic signed complaint");
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveCount(0);
  });

  test("warns on complaint-only patient switch, preserves on cancel, discards on confirm, and leaves sections safe", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1LB-SwitchA-" + suffix, "078" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1LB-SwitchB-" + suffix, "079" + suffix);
    await triageFromQueue(page, patientA);
    await triageFromQueue(page, patientB);
    await openHistory(page, patientA);
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic patient A draft");
    const blocked = await page.evaluate(() => { const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented; });
    expect(blocked).toBe(true);
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientA, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic patient A draft");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
    await page.getByRole("button", { name: "Start encounter" }).click();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByText("Phase 1L-B synthetic patient A draft")).toHaveCount(0);
  });
  test("rejects a duration unit without a duration value before autosave", async ({ page }) => {
    await createConsultation(page, "Phase1LB-PartialDuration-");
    let patchCount = 0;
    page.on("request", (request) => { if (isNotePatch(request)) patchCount += 1; });
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic paired duration");
    await page.getByLabel("Duration unit for presenting complaint 1").selectOption("WEEKS");
    await page.waitForTimeout(3500);
    expect(patchCount).toBe(0);
    await expect(page.getByTestId("presenting-complaint-row-0").getByRole("alert").filter({ hasText: "both a positive duration" })).toBeVisible();
  });

  test("does not copy triage when the History section is revisited", async ({ page }) => {
    await createConsultation(page, "Phase1LB-TriageHydration-");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByTestId("triage-complaint")).toHaveText(SYNTHETIC_TRIAGE);
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("");
  });

  test("omits complaints when signing a clean saved structured list", async ({ page }) => {
    await createConsultation(page, "Phase1LB-CleanSign-");
    await setNkaAndReview(page);
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic clean sign complaint");
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    const signRequest = page.waitForRequest((request) => request.url().endsWith("/sign/") && request.method() === "POST");
    const signResponse = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
    await page.getByRole("button", { name: "Sign consultation" }).click();
    await page.getByRole("button", { name: "Confirm signature" }).click();
    const request = await signRequest;
    const requestBody = JSON.parse(request.postData() ?? "{}") as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(requestBody, "complaints")).toBe(false);
    await signResponse;
    await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
  });

  test("keeps complaint-only dirty state while moving between consultation sections", async ({ page }) => {
    await createConsultation(page, "Phase1LB-Sections-");
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic section-switch draft");
    const blocked = await page.evaluate(() => { const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented; });
    expect(blocked).toBe(true);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByLabel("Presenting complaint", { exact: true })).toHaveValue("Phase 1L-B synthetic section-switch draft");
  });

  test("blocks signing when a complaint duration pair is invalid without a sign request", async ({ page }) => {
    await createConsultation(page, "Phase1LB-InvalidSign-");
    await setNkaAndReview(page);
    let signRequests = 0;
    page.on("request", (request) => { if (request.url().endsWith("/sign/") && request.method() === "POST") signRequests += 1; });
    await steadyFill(page, "Presenting complaint", "Phase 1L-B synthetic invalid sign complaint");
    await page.getByLabel("Duration value for presenting complaint 1").fill("3");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation" }).click();
    await page.getByRole("button", { name: "Confirm signature" }).click();
    await expect(page.getByRole("tab", { name: "History", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("presenting-complaint-row-0").getByRole("alert").filter({ hasText: "both a positive duration" })).toBeVisible();
    expect(signRequests).toBe(0);
  });
});
