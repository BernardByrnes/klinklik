import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";
const SYNTHETIC_COMPLAINT = "Phase 1D verification - synthetic presenting complaint";
const SYNTHETIC_HPI = "Phase 1D verification - synthetic HPI";
const SYNTHETIC_PMH = "Phase 1D verification - synthetic past medical history";
const SYNTHETIC_PSH = "Phase 1D verification - synthetic past surgical history";
const SYNTHETIC_FAMILY = "Phase 1D verification - synthetic family history for patient A";
const SYNTHETIC_SOCIAL = "Phase 1D verification - synthetic social history for patient A";
const SYNTHETIC_NOTE = "Phase 1D verification - synthetic Assessment and Plan.";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt++) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) {
      await page.waitForTimeout(150);
      if ((await locator.inputValue()) === value) return;
    } else {
      await page.waitForTimeout(300);
    }
  }
  throw new Error("Input did not hold its value: " + label);
}

async function login(page: Page) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) {
    await steadyFill(page, "Organisation ID", organisationId);
  }
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
  await expect(page.getByText(patientName).first()).toBeVisible();
  await steadyFill(page, "Chief complaint", "Phase 1D verification - synthetic triage");
  await page.getByRole("button", { name: "Complete triage" }).click();
  await expect(page.getByText(new RegExp("Triage recorded for " + patientName))).toBeVisible();
}

async function openHistory(page: Page, patientName: string) {
  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  const row = page.getByRole("listitem").filter({ hasText: patientName });
  await expect(row).toBeVisible();
  await row.click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Notes", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByRole("tab", { name: "History", exact: true })).toHaveAttribute("aria-selected", "true");
}

async function expectHistory(page: Page, values: {
  complaint: string;
  hpi: string;
  pmh: string;
  psh: string;
  family: string;
  social: string;
}) {
  await expect(page.getByLabel("Presenting complaint")).toHaveValue(values.complaint);
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue(values.hpi);
  await expect(page.getByLabel("Relevant Past Medical History")).toHaveValue(values.pmh);
  await expect(page.getByLabel("Relevant Past Surgical History")).toHaveValue(values.psh);
  await expect(page.getByLabel("Relevant Family History")).toHaveValue(values.family);
  await expect(page.getByLabel("Relevant Social History")).toHaveValue(values.social);
}

test("persists and isolates family and social history", async ({ page }) => {
  await login(page);
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/")) failedRequests.push(request.url());
  });

  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1D-A-" + suffix, "0740" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1D-B-" + suffix, "0741" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  const patientAHistory = {
    complaint: SYNTHETIC_COMPLAINT,
    hpi: SYNTHETIC_HPI,
    pmh: SYNTHETIC_PMH,
    psh: SYNTHETIC_PSH,
    family: SYNTHETIC_FAMILY,
    social: SYNTHETIC_SOCIAL,
  };

  await openHistory(page, patientA);
  await steadyFill(page, "Presenting complaint", SYNTHETIC_COMPLAINT);
  await steadyFill(page, "History of present illness (HPI)", SYNTHETIC_HPI);
  await steadyFill(page, "Relevant Past Medical History", SYNTHETIC_PMH);
  await steadyFill(page, "Relevant Past Surgical History", SYNTHETIC_PSH);
  await steadyFill(page, "Relevant Family History", SYNTHETIC_FAMILY);
  await steadyFill(page, "Relevant Social History", SYNTHETIC_SOCIAL);

  const saveResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await saveResponse).status()).toBe(200);
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expectHistory(page, patientAHistory);

  await page.reload();
  await expect(page).toHaveURL(/\/consultations$/);
  await openHistory(page, patientA);
  await expectHistory(page, patientAHistory);

  await page.locator("nav a[href=\"/consultations\"]").click();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expectHistory(page, {
    complaint: "",
    hpi: "",
    pmh: "",
    psh: "",
    family: "",
    social: "",
  });

  await page.locator("nav a[href=\"/consultations\"]").click();
  await page.getByRole("listitem").filter({ hasText: patientA }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expectHistory(page, patientAHistory);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await steadyFill(page, "Consultation note", SYNTHETIC_NOTE);
  const signResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/sign/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  expect((await signResponse).status()).toBe(200);
  await expect(page.getByText("This consultation is signed and immutable.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByText("This History section is signed and immutable.")).toBeVisible();
  await expect(page.getByText(SYNTHETIC_FAMILY)).toBeVisible();
  await expect(page.getByText(SYNTHETIC_SOCIAL)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Relevant Family History" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Relevant Social History" })).toHaveCount(0);

  const browserStorage = await page.evaluate(() => ({
    local: JSON.stringify({ ...localStorage }),
    session: JSON.stringify({ ...sessionStorage }),
  }));
  expect(browserStorage.local).not.toContain(SYNTHETIC_FAMILY);
  expect(browserStorage.local).not.toContain(SYNTHETIC_SOCIAL);
  expect(browserStorage.session).not.toContain(SYNTHETIC_FAMILY);
  expect(browserStorage.session).not.toContain(SYNTHETIC_SOCIAL);

  await page.setViewportSize({ width: 768, height: 1024 });
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("preserves both writers when stale clients edit different clinical fields", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1DF-Race-" + suffix, "0742" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const initial = {
    family: "Phase 1D-F synthetic original family",
    social: "Phase 1D-F synthetic original social",
  };
  await steadyFill(page, "Relevant Family History", initial.family);
  await steadyFill(page, "Relevant Social History", initial.social);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await expectHistory(stalePage, {
      complaint: "",
      hpi: "",
      pmh: "",
      psh: "",
      family: initial.family,
      social: initial.social,
    });

    const updatedFamily = "Phase 1D-F synthetic updated family";
    const updatedSocial = "Phase 1D-F synthetic updated social";
    const familyRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "POST",
    );
    await steadyFill(page, "Relevant Family History", updatedFamily);
    await page.getByRole("button", { name: "Save draft" }).click();
    const familyBody = JSON.parse((await familyRequest).postData() ?? "{}") as { content?: unknown };
    expect(familyBody.content).toEqual({ family_history: updatedFamily });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 409,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    );
    await steadyFill(stalePage, "Relevant Social History", updatedSocial);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const retry = await retryResponse;
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();
    const conflictBody = JSON.parse((await conflict.request().postData()) ?? "{}") as { content?: unknown };
    const retryBody = JSON.parse((await retry.request().postData()) ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ social_history: updatedSocial });
    expect(retryBody.content).toEqual({ social_history: updatedSocial });
    expect(conflict.request().headers()["if-match"]).toBeTruthy();
    expect(retry.request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    expect(retry.headers()["etag"]).toBeTruthy();
    await expect(stalePage.getByLabel("Relevant Family History")).toHaveValue(updatedFamily);
    await expect(stalePage.getByLabel("Relevant Social History")).toHaveValue(updatedSocial);

    await page.reload();
    await openHistory(page, patientName);
    await expectHistory(page, {
      complaint: "",
      hpi: "",
      pmh: "",
      psh: "",
      family: updatedFamily,
      social: updatedSocial,
    });
  } finally {
    await stalePage.close();
  }
});

test("retains a second edit made while the first draft save is in flight", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1DF-InFlight-" + suffix, "0743" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  let delayFirstSave = true;
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "POST" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  try {
    const family = "Phase 1D-F synthetic in-flight family";
    const social = "Phase 1D-F synthetic in-flight social";
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "POST",
    );
    await steadyFill(page, "Relevant Family History", family);
    await page.getByRole("button", { name: "Save draft" }).click();
    await firstRequest;

    await steadyFill(page, "Relevant Social History", social);
    await expect(page.getByText(/Not saved/)).toBeVisible();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await expect(page.getByText(/Not saved/)).toBeVisible();

    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "POST",
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    const secondBody = JSON.parse((await secondRequest).postData() ?? "{}") as { content?: unknown };
    expect(secondBody.content).toEqual({ social_history: social });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});

test("preserves same-field local draft until explicit retry", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1DF-SameField-" + suffix, "0744" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineFamily = "Phase 1D-F2 synthetic baseline family";
  await steadyFill(page, "Relevant Family History", baselineFamily);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await expect(stalePage.getByLabel("Relevant Family History")).toHaveValue(baselineFamily);

    const updatedFamilyA = "Phase 1D-F2 synthetic writer A family";
    await steadyFill(page, "Relevant Family History", updatedFamilyA);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const updatedFamilyB = "Phase 1D-F2 synthetic writer B family";
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 409,
    );
    await steadyFill(stalePage, "Relevant Family History", updatedFamilyB);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    await expect(stalePage.getByRole("alert").filter({ hasText: "This consultation changed" })).toContainText("Family history");
    const conflictBody = JSON.parse((await conflict.request().postData()) ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ family_history: updatedFamilyB });
    expect(conflict.request().headers()["if-match"]).toBeTruthy();
    expect(conflict.headers()["etag"]).toBeTruthy();
    await expect(stalePage.getByRole("alert").filter({ hasText: "This consultation changed" })).toContainText("preserved");
    await expect(stalePage.getByTestId("conflict-server-value-family_history")).toHaveText(updatedFamilyA);
    await expect(stalePage.getByLabel("Relevant Family History")).toHaveValue(updatedFamilyB);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    expect((await retryResponse).status()).toBe(200);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();

    await page.reload();
    await openHistory(page, patientName);
    await expect(page.getByLabel("Relevant Family History")).toHaveValue(updatedFamilyB);
  } finally {
    await stalePage.close();
  }
});

test("preserves a draft and requires explicit retry after a stale sign", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1DF-StaleSign-" + suffix, "0745" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineFamily = "Phase 1D-F2 synthetic sign baseline family";
  await steadyFill(page, "Relevant Family History", baselineFamily);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);

    let signResponses = 0;
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/sign/") &&
        response.request().method() === "POST" &&
        response.status() !== 401
      ) {
        signResponses += 1;
      }
    });
    const updatedHpi = "Phase 1D-F2 synthetic writer A HPI";
    await steadyFill(page, "History of present illness (HPI)", updatedHpi);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("tab", { name: "Notes", exact: true }).click();
    const staleDraft = "Phase 1D-F2 synthetic stale assessment and plan";
    await steadyFill(stalePage, "Consultation note", staleDraft);
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/sign/") &&
        response.request().method() === "POST" &&
        response.status() === 409,
    );
    await stalePage.getByRole("button", { name: "Sign consultation" }).click();
    await stalePage.getByRole("button", { name: "Confirm signature" }).click();
    const conflict = await conflictResponse;
    await expect(stalePage.getByRole("alert").filter({ hasText: "This consultation changed" })).toContainText("History of present illness");
    expect(signResponses).toBe(1);
    const conflictBody = JSON.parse((await conflict.request().postData()) ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ consultation: staleDraft });
    expect(conflict.request().headers()["if-match"]).toBeTruthy();
    expect(conflict.headers()["etag"]).toBeTruthy();
    await expect(stalePage.getByTestId("conflict-server-value-hpi")).toHaveText(updatedHpi);
    await stalePage.getByRole("tab", { name: "History", exact: true }).click();
    await expect(stalePage.getByLabel("History of present illness (HPI)")).toHaveValue(updatedHpi);
    await stalePage.getByRole("tab", { name: "Notes", exact: true }).click();
    await expect(stalePage.getByLabel("Consultation note")).toHaveValue(staleDraft);
    await expect(stalePage.getByRole("button", { name: "Sign consultation" })).toBeVisible();
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();
    await expect(stalePage.getByText("This consultation is signed and immutable.")).toHaveCount(0);

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/sign/") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Sign consultation" }).click();
    await stalePage.getByRole("button", { name: "Confirm signature" }).click();
    const retry = await retryResponse;
    expect(retry.status()).toBe(200);
    expect(signResponses).toBe(2);
    const signedBody = await retry.json() as { current_version?: number; content?: Record<string, string> };
    expect(signedBody.current_version).toBe(1);
    expect(signedBody.content?.hpi).toBe(updatedHpi);
    expect(signedBody.content?.consultation).toBe(staleDraft);
    await expect(stalePage.getByText("This consultation is signed and immutable.")).toBeVisible();
  } finally {
    await stalePage.close();
  }
});

test("clears conflict comparison when switching patients", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1DF-ConflictA-" + suffix, "0746" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1DF-ConflictB-" + suffix, "0747" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);
  await openHistory(page, patientA);

  const baseline = "Phase 1D-F3 synthetic conflict baseline";
  await steadyFill(page, "Relevant Family History", baseline);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientA);

    const serverFamily = "Phase 1D-F3 synthetic server family";
    await steadyFill(page, "Relevant Family History", serverFamily);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 409,
    );
    await steadyFill(stalePage, "Relevant Family History", "Phase 1D-F3 synthetic local family");
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    await conflictResponse;
    await expect(stalePage.getByTestId("conflict-server-value-family_history")).toHaveText(serverFamily);

    await stalePage.locator('nav a[href="/consultations"]').click();
    await stalePage.getByRole("listitem").filter({ hasText: patientB }).click();
    await stalePage.getByRole("tab", { name: "History", exact: true }).click();
    await stalePage.getByRole("button", { name: "Start encounter" }).click();
    await stalePage.getByRole("tab", { name: "History", exact: true }).click();
    await expect(stalePage.getByTestId("conflict-server-value-family_history")).toHaveCount(0);
    await expect(stalePage.getByText("This consultation changed elsewhere")).toHaveCount(0);
    await expect(stalePage.getByLabel("Relevant Family History")).toHaveValue("");
  } finally {
    await stalePage.close();
  }
});


test("persists, isolates, reloads, signs, and locks general examination", async ({ page }) => {
  await login(page);
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/")) failedRequests.push(request.url());
  });

  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1E-A-" + suffix, "0750" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1E-B-" + suffix, "0751" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  const examination = "Phase 1A verification - synthetic development record: general examination.";
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");

  const saveRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "POST",
  );
  await steadyFill(page, "General Examination", examination);
  await page.getByRole("button", { name: "Save draft" }).click();
  const request = await saveRequest;
  const requestBody = JSON.parse(request.postData() ?? "{}") as { content?: unknown };
  expect(requestBody.content).toEqual({ general_examination: examination });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(examination);

  await page.reload();
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(examination);

  await page.locator('nav a[href="/consultations"]').click();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");

  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(examination);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientA))).toBeVisible();

  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("general-examination-read-only")).toHaveText(examination);
  await expect(page.getByText("This Examination section is signed and immutable.")).toBeVisible();

  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("rebases a stale general examination client after an HPI update", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1E-Concurrency-" + suffix, "0752" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineExamination = "Phase 1E verification - synthetic baseline examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "General Examination", baselineExamination);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("General Examination", { exact: true })).toHaveValue(baselineExamination);

    const updatedHpi = "Phase 1E verification - synthetic HPI from writer A.";
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await steadyFill(page, "History of present illness (HPI)", updatedHpi);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "POST" &&
        response.status() === 409,
    );
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    const updatedExamination = "Phase 1E verification - synthetic examination from writer B.";
    await steadyFill(stalePage, "General Examination", updatedExamination);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ general_examination: updatedExamination });
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("tab", { name: "History", exact: true }).click();
    await expect(stalePage.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(updatedHpi);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("General Examination", { exact: true })).toHaveValue(updatedExamination);

    await page.reload();
    await openHistory(page, patientName);
    await expect(page.getByLabel("History of present illness (HPI)", { exact: true })).toHaveValue(updatedHpi);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(updatedExamination);
  } finally {
    await stalePage.close();
  }
});
