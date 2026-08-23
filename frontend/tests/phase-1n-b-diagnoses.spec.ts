import { expect, test, type Page, type Request } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD;
if (!DEMO_PASSWORD) {
  throw new Error("Set CLINICOPUS_E2E_PASSWORD for local authenticated Playwright tests.");
}

const SYNTHETIC_TRIAGE = "Phase 1N-B verification — synthetic triage complaint";
const SYNTHETIC_COMPLAINT = "Phase 1N-B verification — synthetic presenting complaint";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = label.startsWith("#") ? page.locator(label) : page.getByLabel(label, { exact: true });
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

async function openEncounter(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientName }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByTestId("allergy-banner")).toBeVisible();
}

async function createConsultation(page: Page, prefix: string) {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, prefix + suffix, "078" + suffix);
  await triagePatient(page, patientName);
  await openEncounter(page, patientName);
  return patientName;
}

async function openDiagnosis(page: Page) {
  await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
  await expect(page.getByTestId("diagnosis-section")).toBeVisible();
}

async function setNkaAndReview(page: Page) {
  const statusResponse = page.waitForResponse((response) => response.url().endsWith("/allergy-status/") && response.status() === 200);
  await page.getByRole("button", { name: "No known allergies", exact: true }).click();
  await statusResponse;
  const reviewResponse = page.waitForResponse((response) => response.url().endsWith("/allergies/review/") && response.status() === 200);
  await page.getByRole("button", { name: "Review allergies", exact: true }).click();
  await reviewResponse;
}

async function addComplaint(page: Page, value = SYNTHETIC_COMPLAINT) {
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await steadyFill(page, "Presenting complaint", value);
}

async function saveWorking(page: Page, label: string, code = "", certainty = "") {
  await page.getByRole("button", { name: "Add working diagnosis", exact: true }).click();
  await steadyFill(page, "Diagnosis / clinical impression", label);
  if (code) await steadyFill(page, "Code (optional)", code);
  if (certainty) await steadyFill(page, "Certainty note (optional)", certainty);
  const requestPromise = page.waitForRequest((request) => request.url().endsWith("/diagnoses/") && request.method() === "POST");
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/diagnoses/") && response.status() === 201);
  await page.getByRole("button", { name: "Save working diagnosis", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return { request, response, body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>, data: await response.json() as { diagnoses: Array<{ id: string }> } };
}

async function saveFinal(page: Page, label: string, primary: boolean) {
  await page.getByRole("button", { name: "Add final diagnosis", exact: true }).click();
  await steadyFill(page, "#final-diagnosis-label", label);
  if (primary) await page.getByLabel("Primary diagnosis", { exact: true }).check();
  const requestPromise = page.waitForRequest((request) => request.url().endsWith("/diagnoses/") && request.method() === "POST");
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/diagnoses/") && response.status() === 201);
  await page.getByRole("button", { name: "Save final diagnosis", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return { request, response, body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>, data: await response.json() as { diagnoses: Array<{ id: string }> } };
}

async function saveNoDiagnosis(page: Page, reason: string) {
  await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
  await steadyFill(page, "Reason", reason);
  const requestPromise = page.waitForRequest((request) => request.url().endsWith("/diagnoses/") && request.method() === "POST");
  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/diagnoses/") && response.status() === 201);
  await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
  const request = await requestPromise;
  const response = await responsePromise;
  return { request, response, body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown> };
}

function diagnosisPatchRequests(requests: Request[]) {
  return requests.filter((request) => request.method() === "PATCH" && request.url().includes("/diagnoses/"));
}

test.describe("Phase 1N-B clinician diagnosis workflow", () => {
  test("shows the empty diagnosis section and saves working free text plus optional coded snapshot", async ({ page }) => {
    await createConsultation(page, "Phase1NB-Working-");
    await openDiagnosis(page);
    await expect(page.getByText("No working diagnoses recorded.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add working diagnosis", exact: true })).toBeVisible();

    const freeText = await saveWorking(page, "Phase 1N-B synthetic working diagnosis");
    expect(freeText.body).toMatchObject({
      diagnosis_type: "WORKING",
      label: "Phase 1N-B synthetic working diagnosis",
      is_primary: false,
    });
    expect(Object.prototype.hasOwnProperty.call(freeText.body, "coded")).toBe(false);
    expect(freeText.request.headers()["if-match"]).toBeTruthy();
    await expect(page.getByTestId("diagnosis-section")).toContainText("Working diagnosis");

    const coded = await saveWorking(
      page,
      "Phase 1N-B synthetic coded working diagnosis",
      "SYN-DX-1NB",
      "Phase 1N-B synthetic certainty note",
    );
    expect(coded.body).toMatchObject({
      diagnosis_type: "WORKING",
      label: "Phase 1N-B synthetic coded working diagnosis",
      code: "SYN-DX-1NB",
      certainty_note: "Phase 1N-B synthetic certainty note",
      is_primary: false,
    });
    expect(Object.prototype.hasOwnProperty.call(coded.body, "coded")).toBe(false);
    await expect(page.getByTestId("diagnosis-section")).toContainText("SYN-DX-1NB");
    await expect(page.getByTestId("diagnosis-section")).toContainText("Phase 1N-B synthetic certainty note");
    await expect(page.getByTestId("diagnosis-section").locator("article")).toHaveCount(2);
  });

  test("creates multiple final diagnoses and switches primary with fresh ETags", async ({ page }) => {
    await createConsultation(page, "Phase1NB-Finals-");
    await openDiagnosis(page);
    const first = await saveFinal(page, "Phase 1N-B synthetic primary final", true);
    expect(first.body).toMatchObject({ diagnosis_type: "FINAL", is_primary: true });
    const second = await saveFinal(page, "Phase 1N-B synthetic secondary final", false);
    expect(second.body).toMatchObject({ diagnosis_type: "FINAL", is_primary: false });
    await expect(page.getByTestId("diagnosis-section")).toContainText("Primary");
    await expect(page.getByTestId("diagnosis-section")).toContainText("Secondary");

    const requests: Request[] = [];
    const listener = (request: Request) => {
      if (request.url().includes("/diagnoses/") && request.method() === "PATCH") requests.push(request);
    };
    page.on("request", listener);
    try {
      await page.getByTestId(`diagnosis-${second.data.diagnoses[1].id}`).getByRole("button", { name: "Make primary" }).click();
      await expect.poll(() => diagnosisPatchRequests(requests).length).toBe(2);
      const patches = diagnosisPatchRequests(requests);
      expect(JSON.parse(patches[0].postData() ?? "{}")).toMatchObject({ is_primary: false });
      expect(JSON.parse(patches[1].postData() ?? "{}")).toMatchObject({ is_primary: true });
      expect(patches[0].headers()["if-match"]).not.toBe(patches[1].headers()["if-match"]);
      await expect(page.getByTestId(`diagnosis-${second.data.diagnoses[1].id}`)).toContainText("Primary");
    } finally {
      page.off("request", listener);
    }
  });

  test("edits active diagnoses and soft-removes without DELETE", async ({ page }) => {
    await createConsultation(page, "Phase1NB-EditRemove-");
    await openDiagnosis(page);
    const created = await saveWorking(page, "Phase 1N-B synthetic editable diagnosis");
    const diagnosisId = created.data.diagnoses[0].id;
    const card = page.getByTestId(`diagnosis-${diagnosisId}`);
    await card.getByRole("button", { name: "Edit" }).click();
    await steadyFill(page, "Diagnosis / clinical impression", "Phase 1N-B synthetic edited diagnosis");
    const patchRequest = page.waitForRequest((request) => request.method() === "PATCH" && request.url().includes(`/diagnoses/${diagnosisId}/`));
    const patchResponse = page.waitForResponse((response) => response.status() === 200 && response.url().includes(`/diagnoses/${diagnosisId}/`));
    await page.getByRole("button", { name: "Save diagnosis changes" }).click();
    const patch = await patchRequest;
    expect(JSON.parse(patch.postData() ?? "{}")).toMatchObject({ diagnosis_type: "WORKING", label: "Phase 1N-B synthetic edited diagnosis" });
    expect(patch.headers()["if-match"]).toBeTruthy();
    await patchResponse;
    await expect(page.getByTestId(`diagnosis-${diagnosisId}`)).toContainText("Phase 1N-B synthetic edited diagnosis");

    page.once("dialog", (dialog) => dialog.accept());
    let deleteRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "DELETE") deleteRequests += 1;
    });
    const removeRequest = page.waitForRequest((request) => request.method() === "POST" && request.url().endsWith(`/diagnoses/${diagnosisId}/remove/`));
    const removeResponse = page.waitForResponse((response) => response.status() === 200 && response.url().endsWith(`/diagnoses/${diagnosisId}/remove/`));
    await page.getByTestId(`diagnosis-${diagnosisId}`).getByRole("button", { name: "Remove" }).click();
    const remove = await removeRequest;
    expect(remove.headers()["if-match"]).toBeTruthy();
    await removeResponse;
    expect(deleteRequests).toBe(0);
    await expect(page.getByTestId(`diagnosis-${diagnosisId}`)).toHaveCount(0);
  });

  test("records no final diagnosis, keeps working diagnoses visible, and blocks conflicting final controls", async ({ page }) => {
    await createConsultation(page, "Phase1NB-NoDiagnosis-");
    await openDiagnosis(page);
    await page.getByRole("button", { name: "Record no final diagnosis", exact: true }).click();
    await page.getByRole("button", { name: "Save no final diagnosis", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Enter a reason for recording no final diagnosis." })).toBeVisible();
    await page.getByRole("button", { name: "Cancel", exact: true }).last().click();
    let diagnosisPosts = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/diagnoses/")) diagnosisPosts += 1;
    });
    const saved = await saveNoDiagnosis(page, "Phase 1N-B synthetic reason for no final diagnosis");
    expect(saved.body).toEqual({ diagnosis_type: "NO_DIAGNOSIS", no_diagnosis_reason: "Phase 1N-B synthetic reason for no final diagnosis" });
    await expect(page.getByTestId("no-diagnosis-state")).toContainText("No final diagnosis recorded");
    await expect(page.getByTestId("no-diagnosis-state")).toContainText("Phase 1N-B synthetic reason for no final diagnosis");
    await expect(page.getByRole("button", { name: "Add final diagnosis", exact: true })).toHaveCount(0);

    const working = await saveWorking(page, "Phase 1N-B synthetic working alongside no diagnosis");
    expect(working.body.diagnosis_type).toBe("WORKING");
    await expect(page.getByTestId("diagnosis-section")).toContainText("Phase 1N-B synthetic working alongside no diagnosis");
    await expect(page.getByRole("button", { name: "Promote to final", exact: true })).toHaveCount(0);
    expect(diagnosisPosts).toBe(2);
  });

  test("promotes a working diagnosis explicitly and preserves its content", async ({ page }) => {
    await createConsultation(page, "Phase1NB-Promote-");
    await openDiagnosis(page);
    const created = await saveWorking(page, "Phase 1N-B synthetic promotion label", "SYN-PROMOTE");
    const diagnosisId = created.data.diagnoses[0].id;
    await page.getByTestId(`diagnosis-${diagnosisId}`).getByRole("button", { name: "Promote to final" }).click();
    await expect(page.getByTestId("diagnosis-editor")).toBeVisible();
    await page.getByLabel("Primary diagnosis", { exact: true }).check();
    const requestPromise = page.waitForRequest((request) => request.method() === "PATCH" && request.url().endsWith(`/diagnoses/${diagnosisId}/`));
    const responsePromise = page.waitForResponse((response) => response.status() === 200 && response.url().endsWith(`/diagnoses/${diagnosisId}/`));
    await page.getByTestId("diagnosis-editor").getByRole("button", { name: "Promote to final", exact: true }).click();
    const request = await requestPromise;
    expect(JSON.parse(request.postData() ?? "{}")).toMatchObject({ diagnosis_type: "FINAL", label: "Phase 1N-B synthetic promotion label", code: "SYN-PROMOTE", is_primary: true });
    await responsePromise;
    await expect(page.getByTestId(`diagnosis-${diagnosisId}`)).toContainText("Final diagnosis");
    await expect(page.getByTestId(`diagnosis-${diagnosisId}`)).toContainText("Primary");
  });

  test("blocks signing for working-only and final-without-primary states", async ({ page }) => {
    await createConsultation(page, "Phase1NB-SignWorkingOnly-");
    await setNkaAndReview(page);
    await openDiagnosis(page);
    await saveWorking(page, "Phase 1N-B synthetic working-only sign block");
    await addComplaint(page);
    let signRequests = 0;
    page.on("request", (request) => { if (request.url().endsWith("/sign/") && request.method() === "POST") signRequests += 1; });
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByRole("tab", { name: "Diagnosis", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Record a final diagnosis or document why no final diagnosis was reached before signing.")).toBeVisible();
    expect(signRequests).toBe(0);

    const secondSuffix = Date.now().toString().slice(-6);
    const secondPatient = await registerAndCheckIn(page, "Phase1NB-SignNoPrimary-" + secondSuffix, "078" + secondSuffix);
    await triagePatient(page, secondPatient);
    await openEncounter(page, secondPatient);
    await setNkaAndReview(page);
    await openDiagnosis(page);
    await saveFinal(page, "Phase 1N-B synthetic unselected final", false);
    await addComplaint(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await expect(page.getByRole("tab", { name: "Diagnosis", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Choose one primary final diagnosis before signing.")).toBeVisible();
  });

  test("signs a primary final and makes the diagnosis display read-only", async ({ page }) => {
    await createConsultation(page, "Phase1NB-SignFinal-");
    await setNkaAndReview(page);
    await openDiagnosis(page);
    await saveFinal(page, "Phase 1N-B synthetic signable final", true);
    await addComplaint(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    const signResponse = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await signResponse;
    await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
    await openDiagnosis(page);
    await expect(page.getByTestId("diagnosis-read-only")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add working diagnosis", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Edit", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Remove", exact: true })).toHaveCount(0);
  });

  test("signs a working diagnosis together with an explicit no-diagnosis disposition", async ({ page }) => {
    await createConsultation(page, "Phase1NB-SignNoDiagnosis-");
    await setNkaAndReview(page);
    await openDiagnosis(page);
    await saveNoDiagnosis(page, "Phase 1N-B synthetic no final disposition");
    await saveWorking(page, "Phase 1N-B synthetic provisional sign companion");
    await addComplaint(page);
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page.getByRole("button", { name: "Sign consultation", exact: true }).click();
    const signResponse = page.waitForResponse((response) => response.url().endsWith("/sign/") && response.status() === 200);
    await page.getByRole("button", { name: "Confirm signature", exact: true }).click();
    await signResponse;
    await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();
  });

  test("preserves an unsent diagnosis form across tabs and protects beforeunload", async ({ page }) => {
    await createConsultation(page, "Phase1NB-FormState-");
    await openDiagnosis(page);
    await page.getByRole("button", { name: "Add working diagnosis", exact: true }).click();
    await steadyFill(page, "Diagnosis / clinical impression", "Phase 1N-B synthetic unsent diagnosis form");
    await page.waitForTimeout(250);
    const blocked = await page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(blocked).toBe(true);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
    await expect(page.getByLabel("Diagnosis / clinical impression", { exact: true })).toHaveValue("Phase 1N-B synthetic unsent diagnosis form");
    await page.getByRole("button", { name: "Cancel", exact: true }).last().click();
    const clean = await page.evaluate(() => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(clean).toBe(false);
  });

  test("requires patient-switch confirmation for a diagnosis-only draft and clears it after discard", async ({ page }) => {
    await login(page);
    const suffix = Date.now().toString().slice(-6);
    const patientA = await registerAndCheckIn(page, "Phase1NB-SwitchA-" + suffix, "078" + suffix);
    const patientB = await registerAndCheckIn(page, "Phase1NB-SwitchB-" + suffix, "079" + suffix);
    await triagePatient(page, patientA);
    await triagePatient(page, patientB);
    await openEncounter(page, patientA);
    await openDiagnosis(page);
    await page.getByRole("button", { name: "Add working diagnosis", exact: true }).click();
    await steadyFill(page, "Diagnosis / clinical impression", "Phase 1N-B synthetic patient A unsent diagnosis");

    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientA, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Diagnosis / clinical impression", { exact: true })).toHaveValue("Phase 1N-B synthetic patient A unsent diagnosis");

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context").getByText(patientB, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Diagnosis", exact: true }).click();
    await expect(page.getByRole("button", { name: "Start encounter", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Start encounter", exact: true }).click();
    await openDiagnosis(page);
    await expect(page.getByText("Phase 1N-B synthetic patient A unsent diagnosis")).toHaveCount(0);
  });
});