import { expect, test, type Page, type Request, type Response } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}

const NOTE_PATCH = "**/api/v1/clinic/encounters/*/notes/";
const DISPOSITION_PATCH = "**/api/v1/clinic/encounters/*/disposition/";
const SYNTHETIC_TRIAGE = "Phase 1P-B verification — synthetic triage complaint";
const SYNTHETIC_NOTE = "Phase 1P-B verification — synthetic disposition note";

const DISPOSITIONS = [
  "TREATED_AND_DISCHARGED",
  "REVIEW_SCHEDULED",
  "REFERRED_OUT",
  "ADMITTED_ELSEWHERE",
  "LEFT_AGAINST_ADVICE",
  "DECEASED",
  "OTHER",
] as const;

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

async function addComplaint(page: Page, value = "Phase 1P-B synthetic complaint") {
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

async function saveFinal(page: Page, label = "Phase 1P-B synthetic final diagnosis") {
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

function isDispositionPatch(request: Request) {
  return request.method() === "PATCH" &&
    new URL(request.url()).pathname.endsWith("/disposition/");
}

function isNotePatch(request: Request) {
  return request.method() === "PATCH" &&
    new URL(request.url()).pathname.endsWith("/notes/");
}

function isEncounterGet(response: Response) {
  return response.request().method() === "GET" &&
    new URL(response.url()).pathname.startsWith("/api/v1/clinic/encounters/") && new URL(response.url()).pathname.endsWith("/");
}

async function openTreatment(page: Page) {
  await page.getByRole("tab", { name: "Treatment", exact: true }).click();
  await expect(page.getByTestId("treatment-plan-section")).toBeVisible();
  await expect(page.getByTestId("disposition-section")).toBeVisible();
}

async function saveDisposition(page: Page, value: (typeof DISPOSITIONS)[number], note = "") {
  await page.getByLabel("Disposition", { exact: true }).selectOption(value);
  if (value === "OTHER") await steadyFill(page, "Disposition note", note);
  const requestPromise = page.waitForRequest((request) => isDispositionPatch(request));
  const responsePromise = page.waitForResponse(
    (response) => isDispositionPatch(response.request()) && response.status() === 200,
  );
  await page.getByRole("button", { name: "Save disposition", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return {
    request,
    response,
    body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>,
  };
}

async function switchPatient(page: Page, patientName: string, accept: boolean) {
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toBe("This consultation has unsaved changes. Leave and discard them?");
    if (accept) dialog.accept();
    else dialog.dismiss();
  });
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
}

test.describe("Phase 1P-B encounter disposition frontend", () => {
  test("renders all canonical choices with no default selection", async ({ page }) => {
    await createConsultation(page, "Phase1PB-Choices-");
    await openTreatment(page);
    const select = page.getByLabel("Disposition", { exact: true });
    await expect(select).toHaveValue("");
    await expect(select.locator("option")).toHaveCount(8);
    await expect(select.locator("option").evaluateAll((options) => options.slice(1).map((option) => (option as HTMLOptionElement).value))).resolves.toEqual([...DISPOSITIONS]);
  });

  test("blocks local signing when disposition is empty without sending Sign", async ({ page }) => {
    await createConsultation(page, "Phase1PB-Empty-");
    await prepareSignPrerequisites(page);
    await openTreatment(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    let signRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/sign/")) signRequests += 1;
    });
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();

    await expect(page.getByRole("tab", { name: "Treatment", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Choose a disposition before signing.", { exact: true })).toBeVisible();
    expect(signRequests).toBe(0);
  });

  test("saves TREATED_AND_DISCHARGED with If-Match and adopts authoritative state", async ({ page }) => {
    await createConsultation(page, "Phase1PB-Treated-");
    await openTreatment(page);
    const saved = await saveDisposition(page, "TREATED_AND_DISCHARGED");
    expect(saved.request.headers()["if-match"]).toBeTruthy();
    expect(saved.body).toEqual({ disposition: "TREATED_AND_DISCHARGED", disposition_note: "" });
    const data = await saved.response.json() as Record<string, unknown>;
    expect(typeof data.consultation_etag).toBe("string");
    await expect(page.getByTestId("disposition-section").getByText("Disposition saved.", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Disposition", { exact: true })).toHaveValue("TREATED_AND_DISCHARGED");
  });

  test("requires and preserves an OTHER note verbatim across reload", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1PB-Other-");
    await openTreatment(page);
    await page.getByLabel("Disposition", { exact: true }).selectOption("OTHER");
    await page.getByRole("button", { name: "Save disposition", exact: true }).click();
    await expect(page.getByText("Enter a note for the Other disposition.", { exact: true })).toBeVisible();
    const note = "Phase 1P-B synthetic line one.\nLine two remains exact.";
    const saved = await saveDisposition(page, "OTHER", note);
    expect(saved.body).toEqual({ disposition: "OTHER", disposition_note: note });
    await page.reload();
    await openExistingEncounter(page, patientName);
    await openTreatment(page);
    await expect(page.getByLabel("Disposition", { exact: true })).toHaveValue("OTHER");
    await expect(page.getByLabel("Disposition note", { exact: true })).toHaveValue(note);
  });

  test("shows dependency notices and blocks local sign for review/referral", async ({ page }) => {
    await createConsultation(page, "Phase1PB-Dependencies-");
    await openTreatment(page);
    await saveDisposition(page, "REVIEW_SCHEDULED");
    await expect(page.getByTestId("disposition-follow-up-notice")).toHaveText("A follow-up date is required before this encounter can be signed.");
    await prepareSignPrerequisites(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByText("Record the follow-up date before signing.", { exact: true })).toBeVisible();

    await openTreatment(page);
    await saveDisposition(page, "REFERRED_OUT");
    await expect(page.getByTestId("disposition-referral-notice")).toHaveText("A referral record is required before this encounter can be signed.");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByText("Complete the referral record before signing.", { exact: true })).toBeVisible();
  });

  test("keeps dirty HPI and resumes autosave with the fresh disposition ETag", async ({ page }) => {
    await createConsultation(page, "Phase1PB-DirtyHpi-");
    await page.clock.install();
    await page.clock.pauseAt(Date.now());
    await page.getByRole("tab", { name: "History", exact: true }).click();
    const hpi = "Phase 1P-B synthetic dirty HPI";
    await steadyFill(page, "History of present illness (HPI)", hpi);
    await openTreatment(page);
    const dispositionSaved = await saveDisposition(page, "TREATED_AND_DISCHARGED");
    const noteRequestPromise = page.waitForRequest((request) => isNotePatch(request));
    await page.clock.runFor(3000);
    const noteRequest = await noteRequestPromise;
    const noteBody = JSON.parse(noteRequest.postData() ?? "{}") as Record<string, unknown>;
    expect(noteBody.content).toEqual({ hpi });
    expect(noteRequest.headers()["if-match"]).not.toBe(dispositionSaved.request.headers()["if-match"]);
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  });

  test("performs authoritative Encounter GET on clean 412 and does not replay disposition", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1PB-Clean412-");
    const remotePage = await page.context().newPage();
    try {
      await openExistingEncounter(remotePage, patientName);
      await remotePage.getByRole("tab", { name: "History", exact: true }).click();
      const remoteHpi = "Phase 1P-B synthetic remote HPI after disposition stale revision";
      await steadyFill(remotePage, "History of present illness (HPI)", remoteHpi);
      await remotePage.getByRole("button", { name: "Save draft", exact: true }).click();
      await expect(remotePage.getByText("Consultation draft saved.", { exact: true })).toBeVisible();

      await openTreatment(page);
      await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
      const dispositionPatchCount = { value: 0 };
      page.on("response", (response) => {
        if (isDispositionPatch(response.request()) && response.status() === 412) dispositionPatchCount.value += 1;
      });
      const staleResponse = page.waitForResponse(
        (response) => isDispositionPatch(response.request()) && response.status() === 412,
      );
      const encounterGet = page.waitForResponse(isEncounterGet);
      await page.getByRole("button", { name: "Save disposition", exact: true }).click();
      await staleResponse;
      await encounterGet;
      await expect(page.getByRole("tab", { name: "History", exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await expect(page.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(remoteHpi);
      await expect(page.getByRole("tab", { name: "Treatment", exact: true })).toBeVisible();
      expect(dispositionPatchCount.value).toBe(1);
      await expect(page.getByText("The disposition change was not replayed.", { exact: false })).toBeVisible();
    } finally {
      await remotePage.close();
    }
  });

  test("preserves dirty HPI and exposes remote value after disposition 412", async ({ page }) => {
    const patientName = await createConsultation(page, "Phase1PB-Dirty412-");
    const remotePage = await page.context().newPage();
    try {
      await openExistingEncounter(remotePage, patientName);
      await remotePage.getByRole("tab", { name: "History", exact: true }).click();
      const remoteHpi = "Phase 1P-B synthetic remote HPI conflict";
      await steadyFill(remotePage, "History of present illness (HPI)", remoteHpi);
      await remotePage.getByRole("button", { name: "Save draft", exact: true }).click();
      await expect(remotePage.getByText("Consultation draft saved.", { exact: true })).toBeVisible();

      await page.clock.install();
      await page.clock.pauseAt(Date.now());
      await page.getByRole("tab", { name: "History", exact: true }).click();
      const localHpi = "Phase 1P-B synthetic local HPI conflict";
      await steadyFill(page, "History of present illness (HPI)", localHpi);
      await openTreatment(page);
      await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
      const staleResponse = page.waitForResponse(
        (response) => isDispositionPatch(response.request()) && response.status() === 412,
      );
      const encounterGet = page.waitForResponse(isEncounterGet);
      await page.getByRole("button", { name: "Save disposition", exact: true }).click();
      await staleResponse;
      await encounterGet;
      await expect(page.getByRole("tab", { name: "History", exact: true })).toBeVisible();
      await expect(page.getByRole("tab", { name: "Treatment", exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "History", exact: true }).click();
      await expect(page.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(localHpi);
      await expect(page.getByTestId("conflict-server-value-hpi")).toHaveText(remoteHpi);
      await expect(page.getByText("Not saved — use Save draft.", { exact: true })).toBeVisible();
      await page.getByRole("tab", { name: "Treatment", exact: true }).click();
      await expect(page.getByRole("button", { name: "Save disposition", exact: true })).toBeVisible();
    } finally {
      await remotePage.close();
    }
  });

  test("protects an unsaved disposition during patient switching and clears it after discard", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-7);
    const patientA = await registerAndCheckIn(page, "Phase1PB-SwitchA-" + suffix, "080" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1PB-SwitchB-" + suffix, "081" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await openTreatment(page);
    await page.getByLabel("Disposition", { exact: true }).selectOption("OTHER");
    await steadyFill(page, "Disposition note", SYNTHETIC_NOTE);

    await switchPatient(page, patientB, false);
    await expect(page.getByLabel("Patient and encounter context").getByText(patientA, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Disposition", { exact: true })).toHaveValue("OTHER");
    await expect(page.getByLabel("Disposition note", { exact: true })).toHaveValue(SYNTHETIC_NOTE);

    await switchPatient(page, patientB, true);
    await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Treatment", exact: true }).click();
    await page.getByRole("button", { name: "Start encounter", exact: true }).click();
    await expect(page.getByTestId("allergy-banner")).toBeVisible();
    await openTreatment(page);
    await expect(page.getByLabel("Disposition", { exact: true })).toHaveValue("");
    await expect(page.getByText(SYNTHETIC_NOTE, { exact: true })).toHaveCount(0);
  });

  test("ignores a delayed Patient-A disposition response after switching to Patient B", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-7);
    const patientA = await registerAndCheckIn(page, "Phase1PB-DelayedA-" + suffix, "082" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1PB-DelayedB-" + suffix, "083" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await openTreatment(page);

    let firstRequest = true;
    let releaseResponse: (() => void) | null = null;
    const responsePaused = new Promise<void>((resolve) => { releaseResponse = resolve; });
    await page.route(DISPOSITION_PATCH, async (route) => {
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
      const requestSeen = page.waitForRequest((request) => isDispositionPatch(request));
      await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
      await page.getByRole("button", { name: "Save disposition", exact: true }).click();
      await requestSeen;
      await switchPatient(page, patientB, true);
      await page.getByRole("tab", { name: "Treatment", exact: true }).click();
      await page.getByRole("button", { name: "Start encounter", exact: true }).click();
      await expect(page.getByTestId("allergy-banner")).toBeVisible();
      releaseResponse?.();
      await page.waitForTimeout(300);
      await openTreatment(page);
      await expect(page.getByLabel("Disposition", { exact: true })).toHaveValue("");
      await expect(page.getByText("Disposition saved.", { exact: true })).toHaveCount(0);
    } finally {
      releaseResponse?.();
      await page.unroute(DISPOSITION_PATCH);
    }
  });

  test("beforeunload protects disposition-only drafts and cancel clears the warning", async ({ page }) => {
    await createConsultation(page, "Phase1PB-BeforeUnload-");
    await openTreatment(page);
    await page.getByLabel("Disposition", { exact: true }).selectOption("TREATED_AND_DISCHARGED");
    const blocked = await page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(blocked).toBe(true);
    await page.getByRole("button", { name: "Cancel changes", exact: true }).click();
    const unblocked = await page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(unblocked).toBe(false);
  });

  test("signs a treated encounter and displays the disposition read-only", async ({ page }) => {
    await createConsultation(page, "Phase1PB-Signed-");
    await prepareSignPrerequisites(page);
    await openTreatment(page);
    await saveDisposition(page, "TREATED_AND_DISCHARGED");
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByText(/This consultation is signed and immutable\./)).toBeVisible();
    await openTreatment(page);
    await expect(page.getByTestId("disposition-read-only")).toBeVisible();
    await expect(page.getByTestId("disposition-read-only-value")).toHaveText("Treated and discharged");
    await expect(page.getByLabel("Disposition", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Save disposition", exact: true })).toHaveCount(0);
  });
});