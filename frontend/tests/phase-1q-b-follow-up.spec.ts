import { expect, test, type Page, type Request, type Response } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}

const FOLLOW_UP_PATCH = "**/api/v1/clinic/encounters/*/follow-up/";
const SYNTHETIC_TRIAGE = "Phase 1Q-B verification — synthetic triage complaint";
const SYNTHETIC_FOLLOW_UP = "Phase 1Q-B verification — synthetic follow-up instruction";
const SYNTHETIC_COMPLAINT = "Phase 1Q-B verification — synthetic complaint";

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
  await expect(page).toHaveURL(/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/overview$/);
}

async function registerAndCheckIn(page: Page, firstName: string, phone: string) {
  await page.locator('nav a[href="/patients"]').click();
  await expect(page).toHaveURL(/patients$/);
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
  await expect(page).toHaveURL(/queue$/);
  await page.getByLabel("Filter queue").fill(patientName);
  const row = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Claim" }).click();
  await expect(row.getByText("Called")).toBeVisible();
  await row.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/triage/);
  await steadyFill(page, "Chief complaint", SYNTHETIC_TRIAGE);
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText(new RegExp("Triage recorded for " + patientName))).toBeVisible();
}

async function openEncounter(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const startButton = page.getByRole("button", { name: "Start encounter", exact: true });
  if (await startButton.count() > 0) {
    await startButton.click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
  }
}

async function openExistingEncounter(page: Page, patientName: string) {
  await page.goto("/consultations");
  await expect(page).toHaveURL(/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const startButton = page.getByRole("button", { name: "Start encounter", exact: true });
  if (await startButton.count() > 0) {
    await startButton.click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
  }
}

async function createConsultation(page: Page, prefix: string) {
  await login(page);
  const suffix = Date.now().toString().slice(-7);
  const patientName = await registerAndCheckIn(page, prefix + suffix, "078" + suffix);
  await triagePatient(page, patientName);
  await openEncounter(page, patientName);
  return patientName;
}

async function saveDraft(page: Page) {
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/notes/") && response.request().method() === "PATCH" && response.status() === 200,
  );
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await responsePromise;
}

async function addComplaint(page: Page, value = SYNTHETIC_COMPLAINT) {
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", value);
  await saveDraft(page);
}

async function setNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await statusResponse;
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
}

async function saveFinal(page: Page, label = "Phase 1Q-B synthetic final diagnosis") {
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

async function prepareSignPrerequisites(page: Page) {
  await addComplaint(page);
  await setNkaAndReview(page);
  await saveFinal(page);
}

async function openTreatment(page: Page) {
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  await expect(page.getByTestId("treatment-plan-section")).toBeVisible();
  await expect(page.getByTestId("disposition-section")).toBeVisible();
  await expect(page.getByTestId("follow-up-section")).toBeVisible();
}

async function saveDisposition(page: Page, value: string) {
  await page.getByLabel("Disposition", { exact: true }).selectOption(value);
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/disposition/") && response.request().method() === "PATCH" && response.status() === 200,
  );
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  await responsePromise;
}

async function saveFollowUp(page: Page) {
  const requestPromise = page.waitForRequest(
    (request) => request.method() === "PATCH" && new URL(request.url()).pathname.endsWith("/follow-up/"),
  );
  const responsePromise = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && new URL(response.url()).pathname.endsWith("/follow-up/"),
  );
  await page.getByRole("button", { name: "Save follow-up", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return { request, response };
}

function isFollowUpPatch(request: Request) {
  return request.method() === "PATCH" &&
    new URL(request.url()).pathname.endsWith("/follow-up/");
}

function isEncounterGet(response: Response) {
  const pathname = new URL(response.url()).pathname;
  return response.request().method() === "GET" &&
    pathname.startsWith("/api/v1/clinic/encounters/") &&
    pathname.endsWith("/");
}

async function switchPatient(page: Page, patientName: string, accept: boolean) {
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toBe("This consultation has unsaved changes. Leave and discard them?");
    if (accept) dialog.accept();
    else dialog.dismiss();
  });
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
}

test.describe("Phase 1Q-B follow-up clinician UI", () => {
  test("saves the date and instructions and preserves them across reload", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1QB-RoundTrip-");
    await openTreatment(page);
    const date = "2099-12-31";
    await steadyFill(page, "Follow-up date", date);
    await steadyFill(page, "Instructions", SYNTHETIC_FOLLOW_UP);
    const saved = await saveFollowUp(page);
    expect(saved.response.status()).toBe(200);
    expect(saved.request.headers()["if-match"]).toBeTruthy();
    expect(JSON.parse(saved.request.postData() ?? "{}")).toEqual({
      recommended_date: date,
      instructions: SYNTHETIC_FOLLOW_UP,
    });
    const responseData = await saved.response.json() as Record<string, unknown>;
    expect(typeof responseData.consultation_etag).toBe("string");
    await expect(page.getByTestId("follow-up-section").getByText("Follow-up saved.", { exact: true })).toBeVisible();

    await page.reload();
    await openExistingEncounter(page, patientName);
    await openTreatment(page);
    await expect(page.getByLabel("Follow-up date", { exact: true })).toHaveValue(date);
    await expect(page.getByLabel("Instructions", { exact: true })).toHaveValue(SYNTHETIC_FOLLOW_UP);
  });

  test("requires If-Match and adopts the fresh shared consultation ETag", async ({ page }) => {
    await createConsultation(page, "Phase1QB-Etag-");
    await openTreatment(page);
    await steadyFill(page, "Follow-up date", "2099-12-30");
    await steadyFill(page, "Instructions", SYNTHETIC_FOLLOW_UP);
    const saved = await saveFollowUp(page);
    expect(saved.request.headers()["if-match"]).toBeTruthy();
    const responseData = await saved.response.json() as Record<string, unknown>;
    expect(typeof responseData.consultation_etag).toBe("string");
    await expect(page.getByTestId("follow-up-section").getByText("Follow-up saved.", { exact: true })).toBeVisible();
  });

  test("blocks REVIEW_SCHEDULED signing locally when no saved follow-up date exists", async ({ page }) => {
    await createConsultation(page, "Phase1QB-Missing-");
    await prepareSignPrerequisites(page);
    await openTreatment(page);
    await saveDisposition(page, "REVIEW_SCHEDULED");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();

    let signRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/sign/")) signRequests += 1;
    });
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();

    await expect(page.getByRole("tab", { name: "Treatment", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Record the follow-up date before signing.", { exact: true })).toBeVisible();
    expect(signRequests).toBe(0);
  });

  test("allows REVIEW_SCHEDULED signing after a follow-up date is saved and then displays read-only", async ({ page }) => {
    await createConsultation(page, "Phase1QB-Signable-");
    await prepareSignPrerequisites(page);
    await openTreatment(page);
    await saveDisposition(page, "REVIEW_SCHEDULED");
    await steadyFill(page, "Follow-up date", "2099-12-29");
    await steadyFill(page, "Instructions", SYNTHETIC_FOLLOW_UP);
    await saveFollowUp(page);

    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByText(/This consultation is signed and immutable./)).toBeVisible();

    await openTreatment(page);
    await expect(page.getByTestId("follow-up-read-only")).toBeVisible();
    await expect(page.getByTestId("follow-up-read-only-date")).toHaveText("2099-12-29");
    await expect(page.getByTestId("follow-up-read-only-instructions")).toHaveText(SYNTHETIC_FOLLOW_UP);
    await expect(page.getByLabel("Follow-up date", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Save follow-up", exact: true })).toHaveCount(0);
  });

  test("reconciles a stale follow-up save from an authoritative Encounter GET without replay", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1QB-Clean412-");
    const remotePage = await page.context().newPage();
    try {
      await openExistingEncounter(remotePage, patientName);
      await remotePage.getByRole("tab", { name: "History", exact: true }).click();
      const remoteHpi = "Phase 1Q-B synthetic remote HPI";
      await steadyFill(remotePage, "History of present illness (HPI)", remoteHpi);
      await remotePage.getByRole("button", { name: "Save draft", exact: true }).click();
      await expect(remotePage.getByText("Consultation draft saved.", { exact: true })).toBeVisible();

      await openTreatment(page);
      await steadyFill(page, "Follow-up date", "2099-12-28");
      await steadyFill(page, "Instructions", SYNTHETIC_FOLLOW_UP);
      const followUp412 = page.waitForResponse(
        (response) => isFollowUpPatch(response.request()) && response.status() === 412,
      );
      const encounterGet = page.waitForResponse(isEncounterGet);
      const followUpResponses: Response[] = [];
      page.on("response", (response) => {
        if (isFollowUpPatch(response.request())) followUpResponses.push(response);
      });
      await page.getByRole("button", { name: "Save follow-up", exact: true }).click();
      await followUp412;
      await encounterGet;

      expect(followUpResponses.filter((response) => response.status() === 412)).toHaveLength(1);
      expect(followUpResponses.filter((response) => response.status() >= 200 && response.status() < 300)).toHaveLength(0);
      await expect(page.getByLabel("Follow-up date", { exact: true })).toHaveValue("2099-12-28");
      await expect(page.getByLabel("Instructions", { exact: true })).toHaveValue(SYNTHETIC_FOLLOW_UP);
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await expect(page.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(remoteHpi);
      await expect(page.getByText("The follow-up change was not replayed.", { exact: false })).toBeVisible();
    } finally {
      await remotePage.close();
    }
  });

  test("protects follow-up drafts during beforeunload and delayed Patient-A switching", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-7);
    const patientA = await registerAndCheckIn(page, "Phase1QB-DelayedA-" + suffix, "084" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1QB-DelayedB-" + suffix, "085" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await openTreatment(page);

    await steadyFill(page, "Follow-up date", "2099-12-27");
    await steadyFill(page, "Instructions", SYNTHETIC_FOLLOW_UP);
    const blocked = await page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(blocked).toBe(true);

    let firstRequest = true;
    let releaseResponse: (() => void) | null = null;
    const responsePaused = new Promise<void>((resolve) => { releaseResponse = resolve; });
    await page.route(FOLLOW_UP_PATCH, async (route) => {
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
      const requestSeen = page.waitForRequest((request) => isFollowUpPatch(request));
      await page.getByRole("button", { name: "Save follow-up", exact: true }).click();
      await requestSeen;
      await switchPatient(page, patientB, true);
      await page.getByRole("tab", { name: "Treatment", exact: true }).click();
      await page.getByRole("button", { name: "Start encounter", exact: true }).click();
      await expect(page.getByTestId("allergy-banner")).toBeVisible();

      releaseResponse?.();
      await page.waitForTimeout(500);
      await openTreatment(page);
      await expect(page.getByLabel("Follow-up date", { exact: true })).toHaveValue("");
      await expect(page.getByLabel("Instructions", { exact: true })).toHaveValue("");
      await expect(page.getByText(SYNTHETIC_FOLLOW_UP, { exact: true })).toHaveCount(0);
      const unblocked = await page.evaluate(() => {
        const event = new Event("beforeunload", { cancelable: true });
        window.dispatchEvent(event);
        return event.defaultPrevented;
      });
      expect(unblocked).toBe(false);
    } finally {
      releaseResponse?.();
      await page.unroute(FOLLOW_UP_PATCH);
    }
  });
});