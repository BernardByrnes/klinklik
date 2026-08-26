
import { expect, test, type Page, type Request } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}

const NOTE_PATCH = "**/api/v1/clinic/encounters/*/notes/";
const SYNTHETIC_TRIAGE = "Phase 1O-B verification — synthetic triage complaint";

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

async function triagePatient(page: Page, patientName: string) {
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

async function openTreatment(page: Page) {
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  await expect(page.getByTestId("treatment-plan-section")).toBeVisible();
}

async function openEncounter(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const startButton = page.getByRole("button", { name: "Start encounter", exact: true });
  if (await startButton.count() > 0) {
    await startButton.click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
  }
  await openTreatment(page);
}

async function openExistingEncounter(page: Page, patientName: string) {
  await page.goto("/consultations");
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const startButton = page.getByRole("button", { name: "Start encounter", exact: true });
  if (await startButton.count() > 0) {
    await startButton.click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
  }
  await openTreatment(page);
}

async function saveTreatedDisposition(page: Page) {
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/disposition/") && response.status() === 200,
  );
  await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  await responsePromise;
}

async function createConsultation(page: Page, prefix: string) {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, prefix + suffix, "078" + suffix);
  await triagePatient(page, patientName);
  await openEncounter(page, patientName);
  await saveTreatedDisposition(page);
  return patientName;
}

function isNotePatch(request: Request) {
  return request.method() === "PATCH" &&
    /\/api\/v1\/clinic\/encounters\/[^/]+\/notes\/$/.test(new URL(request.url()).pathname);
}

async function saveTreatment(page: Page, value: string) {
  await steadyFill(page, "Treatment plan", value);
  const requestPromise = page.waitForRequest((request) => isNotePatch(request));
  const responsePromise = page.waitForResponse(
    (response) => isNotePatch(response.request()) && response.status() === 200,
  );
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return {
    request,
    response,
    body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>,
  };
}

async function setNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await statusResponse;
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
}

async function saveFinal(page: Page, label: string) {
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await page.getByRole("button", { name: "Add final diagnosis", exact: true }).click();
  await page.locator("#final-diagnosis-label").fill(label);
  await page.getByLabel("Primary diagnosis", { exact: true }).check();
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/diagnoses/") && response.status() === 201,
  );
  await page.getByRole("button", { name: "Save final diagnosis", exact: true }).click();
  await responsePromise;
}

async function addComplaint(page: Page, value: string) {
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", value);
}

test.describe("Phase 1O-B treatment plan frontend", () => {
  test("edits, manually saves, and reloads treatment-plan content", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1OB-Manual-");
    const value = "Phase 1O-B synthetic treatment plan";
    const saved = await saveTreatment(page, value);

    expect(saved.body.content).toEqual({ treatment_plan: value });
    expect(saved.body.complaints).toBeUndefined();
    expect(saved.request.headers()["if-match"]).toBeTruthy();
    expect(saved.request.headers()["x-klinklik-autosave"]).toBeUndefined();
    await expect(page.getByText("Consultation draft saved.", { exact: true })).toBeVisible();

    await page.reload();
    await openExistingEncounter(page, patientName);
    await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(value);
  });

  test("preserves multiline treatment instructions across section switching", async ({ page }) => {
    await createConsultation(page, "Phase1OB-Multiline-");
    const value = "Phase 1O-B synthetic instruction line one.\nLine two stays separate.\nLine three stays exact.";
    await saveTreatment(page, value);
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await page.getByRole("tab", { name: "Treatment", exact: true }).click();
    await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(value);
  });

  test("keeps treatment-plan focus and characters during incremental keyboard typing", async ({ page }) => {
    await createConsultation(page, "Phase1OB-Incremental-");
    const treatmentPlan = page.getByLabel("Treatment plan", { exact: true });
    const value = "Review in 7 days";
    let typed = "";

    await treatmentPlan.click();
    for (const character of value) {
      await treatmentPlan.pressSequentially(character);
      typed += character;
      await expect(treatmentPlan).toBeFocused();
      await expect(treatmentPlan).toHaveValue(typed);
    }
  });

  test("keeps the caret at the end when appending to an existing treatment plan", async ({ page }) => {
    await createConsultation(page, "Phase1OB-Caret-");
    const initialValue = "Supportive care";
    const appendedValue = " and hydration";
    await saveTreatment(page, initialValue);

    const treatmentPlan = page.getByLabel("Treatment plan", { exact: true });
    await treatmentPlan.click();
    await treatmentPlan.press("End");
    let typed = initialValue;
    for (const character of appendedValue) {
      await treatmentPlan.pressSequentially(character);
      typed += character;
      await expect(treatmentPlan).toBeFocused();
      await expect(treatmentPlan).toHaveValue(typed);
    }
    await expect(treatmentPlan).toHaveValue("Supportive care and hydration");
  });
  test("autosaves only treatment_plan with the existing marker and saved status", async ({ page }) => {
    await createConsultation(page, "Phase1OB-Autosave-");
    const value = "Phase 1O-B synthetic autosave plan";
    const requestPromise = page.waitForRequest((request) => isNotePatch(request));
    await steadyFill(page, "Treatment plan", value);
    const request = await requestPromise;
    const body = JSON.parse(request.postData() ?? "{}") as Record<string, unknown>;

    expect(body.content).toEqual({ treatment_plan: value });
    expect(request.headers()["if-match"]).toBeTruthy();
    expect(request.headers()["x-klinklik-autosave"]).toBe("1");
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  });

  test("submits a dirty-only treatment-plan payload without unrelated note fields", async ({ page }) => {
    await createConsultation(page, "Phase1OB-DirtyOnly-");
    const value = "Phase 1O-B synthetic dirty-only plan";
    const saved = await saveTreatment(page, value);
    const content = saved.body.content as Record<string, unknown>;

    expect(Object.keys(content)).toEqual(["treatment_plan"]);
    expect(content).not.toHaveProperty("hpi");
    expect(content).not.toHaveProperty("consultation");
    expect(content).not.toHaveProperty("general_examination");
  });

  test("preserves a newer treatment-plan edit while an earlier save is in flight", async ({ page }) => {
    await createConsultation(page, "Phase1OB-InFlight-");
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
      const firstValue = "Phase 1O-B synthetic in-flight first value";
      const currentValue = "Phase 1O-B synthetic in-flight current value";
      const firstRequestSeen = page.waitForRequest((request) => isNotePatch(request));
      await steadyFill(page, "Treatment plan", firstValue);
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await firstRequestSeen;
      await steadyFill(page, "Treatment plan", currentValue);
      await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(currentValue);
      await expect(page.getByText("Not saved — use Save draft.", { exact: true })).toBeVisible();
      releaseResponse?.();

      const secondRequest = await page.waitForRequest((request) => isNotePatch(request));
      const body = JSON.parse(secondRequest.postData() ?? "{}") as Record<string, unknown>;
      expect(body.content).toEqual({ treatment_plan: currentValue });
      await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("preserves local treatment text and blocks automatic replay on same-field conflict", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1OB-Conflict-");
    const remotePage = await page.context().newPage();
    try {
      await openExistingEncounter(remotePage, patientName);
      const remoteValue = "Phase 1O-B synthetic remote treatment plan";
      await saveTreatment(remotePage, remoteValue);
      await page.clock.install();
      await page.clock.pauseAt(Date.now());

      const localValue = "Phase 1O-B synthetic local treatment plan";
      await steadyFill(page, "Treatment plan", localValue);
      let conflictResponses = 0;
      page.on("response", (response) => {
        if (isNotePatch(response.request()) && [409, 412].includes(response.status())) conflictResponses += 1;
      });
      const conflictResponse = page.waitForResponse(
        (response) => isNotePatch(response.request()) && response.status() === 412,
      );
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await conflictResponse;

      await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(localValue);
      await expect(page.getByTestId("conflict-server-value-treatment_plan")).toHaveText(remoteValue);
      await expect(page.getByText("Not saved — use Save draft.", { exact: true })).toBeVisible();
      await page.waitForTimeout(2500);
      expect(conflictResponses).toBe(1);
    } finally {
      await remotePage.close();
    }
  });

  test("rebases a non-overlapping remote HPI change while preserving the local treatment plan", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1OB-Rebase-");
    const remotePage = await page.context().newPage();
    try {
      await openExistingEncounter(remotePage, patientName);
      const remoteHpi = "Phase 1O-B synthetic remote HPI";
      await remotePage.getByRole("tab", { name: "History", exact: true }).click();
      await steadyFill(remotePage, "History of present illness (HPI)", remoteHpi);
      await remotePage.getByRole("button", { name: "Save draft", exact: true }).click();
      await expect(remotePage.getByText("Consultation draft saved.", { exact: true })).toBeVisible();
      await page.clock.install();
      await page.clock.pauseAt(Date.now());

      const localPlan = "Phase 1O-B synthetic local treatment after rebase";
      await steadyFill(page, "Treatment plan", localPlan);
      const requests: Request[] = [];
      page.on("response", (response) => {
        if (isNotePatch(response.request()) && response.status() !== 401) requests.push(response.request());
      });
      const rebasedSave = page.waitForResponse(
        (response) => isNotePatch(response.request()) && response.status() === 200,
      );
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await rebasedSave;

      await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(localPlan);
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await expect(page.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(remoteHpi);
      expect(requests.length).toBe(2);
      expect(JSON.parse(requests[1].postData() ?? "{}")).toMatchObject({ content: { treatment_plan: localPlan } });
      expect(JSON.parse(requests[1].postData() ?? "{}").content).not.toHaveProperty("hpi");
      expect(requests[0].headers()["if-match"]).not.toBe(requests[1].headers()["if-match"]);
    } finally {
      await remotePage.close();
    }
  });

  test("protects a dirty treatment plan during patient switch and clears it after confirmed discard", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1OB-SwitchA-" + suffix, "080" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1OB-SwitchB-" + suffix, "081" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await page.clock.install();
    await page.clock.pauseAt(Date.now());
    const localValue = "Phase 1O-B synthetic Patient A unsaved treatment plan";
    await steadyFill(page, "Treatment plan", localValue);

    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientA, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue(localValue);

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Treatment", exact: true }).click();
    await page.getByRole("button", { name: "Start encounter", exact: true }).click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
    await openTreatment(page);
    await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue("");
    await expect(page.getByText(localValue, { exact: true })).toHaveCount(0);
  });

  test("ignores a delayed Patient-A save response after switching to Patient B", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1OB-DelayedA-" + suffix, "082" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1OB-DelayedB-" + suffix, "083" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await page.clock.install();
    await page.clock.pauseAt(Date.now());

    let firstRequest = true;
    let releaseResponse: (() => void) | null = null;
    let responseReady: (() => void) | null = null;
    let responseDelivered: (() => void) | null = null;
    const responsePaused = new Promise<void>((resolve) => { releaseResponse = resolve; });
    const responseFetched = new Promise<void>((resolve) => { responseReady = resolve; });
    const responseFinished = new Promise<void>((resolve) => { responseDelivered = resolve; });

    await page.route(NOTE_PATCH, async (route) => {
      if (route.request().method() === "PATCH" && firstRequest) {
        firstRequest = false;
        const response = await route.fetch();
        responseReady?.();
        await responsePaused;
        await route.fulfill({ response });
        responseDelivered?.();
        return;
      }
      await route.continue();
    });

    try {
      const patientAValue = "Phase 1O-B synthetic delayed Patient A treatment plan";
      const requestSeen = page.waitForRequest((request) => isNotePatch(request));
      await steadyFill(page, "Treatment plan", patientAValue);
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await requestSeen;
      await responseFetched;

      page.once("dialog", (dialog) => {
        expect(dialog.message()).toBe("This consultation has unsaved changes. Leave and discard them?");
        dialog.accept();
      });
      await page.getByRole("listitem").filter({ hasText: patientB }).click();
      await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await page.getByRole("button", { name: "Start encounter", exact: true }).click();
      await expect(page.getByTestId("allergy-banner")).toBeVisible();
      await openTreatment(page);
      await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue("");

      releaseResponse?.();
      await responseFinished;
      await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
      await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveValue("");
      await expect(page.getByText(patientAValue, { exact: true })).toHaveCount(0);
      await expect(page.getByText("Consultation draft saved.", { exact: true })).toHaveCount(0);
    } finally {
      await page.unroute(NOTE_PATCH);
    }
  });

  test("renders signed treatment plan read-only with editing and autosave unavailable", async ({ page }) => {
    await createConsultation(page, "Phase1OB-Signed-");
    const value = "Phase 1O-B synthetic signed treatment instructions.\nKeep exact line breaks.";
    await saveTreatment(page, value);
    await setNkaAndReview(page);
    await saveFinal(page, "Phase 1O-B synthetic signable final");
    await addComplaint(page, "Phase 1O-B synthetic signing complaint");

    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    const signResponse = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await signResponse;

    await openTreatment(page);
    await expect(page.getByTestId("treatment-plan-read-only")).toHaveText(value);
    await expect(page.getByLabel("Treatment plan", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Save draft", exact: true })).toHaveCount(0);
  });
});
