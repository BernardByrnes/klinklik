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

async function ensureSyntheticComplaint(page: Page) {
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const complaint = page.getByLabel("Presenting complaint", { exact: true });
  if ((await complaint.inputValue()) === SYNTHETIC_COMPLAINT) return;
  await steadyFill(page, "Presenting complaint", SYNTHETIC_COMPLAINT);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();
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
      response.request().method() === "PATCH",
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
        request.method() === "PATCH",
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
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
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
    if (route.request().method() === "PATCH" && delayFirstSave) {
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
        request.method() === "PATCH",
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
        request.method() === "PATCH",
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
        response.request().method() === "PATCH" &&
        response.status() === 412,
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
        response.request().method() === "PATCH" &&
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

  await ensureSyntheticComplaint(page);
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
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    await steadyFill(stalePage, "Relevant Family History", "Phase 1D-F3 synthetic local family");
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    await conflictResponse;
    await expect(stalePage.getByTestId("conflict-server-value-family_history")).toHaveText(serverFamily);

    await stalePage.locator('nav a[href="/consultations"]').click();
    stalePage.once("dialog", async (dialog) => {
      await dialog.accept();
    });
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
  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");

  const saveRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
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
        response.request().method() === "PATCH" &&
        response.status() === 412,
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


test("persists, isolates, reloads, signs, and locks cardiovascular and respiratory examination", async ({ page }) => {
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
  const patientA = await registerAndCheckIn(page, "Phase1F-A-" + suffix, "0760" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1F-B-" + suffix, "0761" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  const general = "Phase 1F verification - synthetic general examination.";
  const cardiovascular = "Phase 1F verification - synthetic cardiovascular examination.";
  const respiratory = "Phase 1F verification - synthetic respiratory examination.";

  await openHistory(page, patientA);
  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");

  const generalRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "General Examination", general);
  await page.getByRole("button", { name: "Save draft" }).click();
  const generalBody = JSON.parse((await generalRequest).postData() ?? "{}") as { content?: unknown };
  expect(generalBody.content).toEqual({ general_examination: general });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const systemsRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "Cardiovascular Examination", cardiovascular);
  await steadyFill(page, "Respiratory Examination", respiratory);
  await page.getByRole("button", { name: "Save draft" }).click();
  const systemsBody = JSON.parse((await systemsRequest).postData() ?? "{}") as { content?: unknown };
  expect(systemsBody.content).toEqual({
    cardiovascular_examination: cardiovascular,
    respiratory_examination: respiratory,
  });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);

  await page.reload();
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);

  await page.locator('nav a[href="/consultations"]').click();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");

  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientB))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("general-examination-read-only")).toHaveText("Not recorded.");
  await expect(page.getByTestId("cardiovascular-examination-read-only")).toHaveText("Not recorded.");
  await expect(page.getByTestId("respiratory-examination-read-only")).toHaveText("Not recorded.");

  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientA))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("general-examination-read-only")).toHaveText(general);
  await expect(page.getByTestId("cardiovascular-examination-read-only")).toHaveText(cardiovascular);
  await expect(page.getByTestId("respiratory-examination-read-only")).toHaveText(respiratory);
  await expect(page.getByText("This Examination section is signed and immutable.")).toBeVisible();

  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("rebases a stale respiratory examination after a general examination update", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1F-Concurrency-" + suffix, "0762" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineGeneral = "Phase 1F verification - synthetic baseline general examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "General Examination", baselineGeneral);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("General Examination", { exact: true })).toHaveValue(baselineGeneral);

    const updatedGeneral = "Phase 1F verification - synthetic general examination from writer A.";
    await steadyFill(page, "General Examination", updatedGeneral);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    const updatedRespiratory = "Phase 1F verification - synthetic respiratory examination from writer B.";
    await steadyFill(stalePage, "Respiratory Examination", updatedRespiratory);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const retry = await retryResponse;
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ respiratory_examination: updatedRespiratory });
    expect(retryBody.content).toEqual({ respiratory_examination: updatedRespiratory });
    expect(retry.request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();
    await expect(stalePage.getByLabel("General Examination", { exact: true })).toHaveValue(updatedGeneral);
    await expect(stalePage.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(updatedRespiratory);

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(updatedGeneral);
    await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(updatedRespiratory);
  } finally {
    await stalePage.close();
  }
});

test("preserves same-field cardiovascular draft until explicit retry", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1F-SameField-" + suffix, "0763" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineCardiovascular = "Phase 1F verification - synthetic baseline cardiovascular examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "Cardiovascular Examination", baselineCardiovascular);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(baselineCardiovascular);

    const updatedCardiovascularA = "Phase 1F verification - synthetic cardiovascular examination from writer A.";
    await steadyFill(page, "Cardiovascular Examination", updatedCardiovascularA);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    let nonAuthWrites = 0;
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() !== 401
      ) {
        nonAuthWrites += 1;
      }
    });
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const updatedCardiovascularB = "Phase 1F verification - synthetic local cardiovascular examination.";
    await steadyFill(stalePage, "Cardiovascular Examination", updatedCardiovascularB);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    await page.waitForTimeout(250);
    expect(nonAuthWrites).toBe(1);
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ cardiovascular_examination: updatedCardiovascularB });
    await expect(stalePage.getByTestId("conflict-server-value-cardiovascular_examination")).toHaveText(updatedCardiovascularA);
    await expect(stalePage.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(updatedCardiovascularB);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const retry = await retryResponse;
    expect(retry.status()).toBe(200);
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(retryBody.content).toEqual({ cardiovascular_examination: updatedCardiovascularB });

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(updatedCardiovascularB);
  } finally {
    await stalePage.close();
  }
});

test("retains a respiratory edit made while a cardiovascular save is in flight", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1F-InFlight-" + suffix, "0764" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  let delayFirstSave = true;
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  try {
    const cardiovascular = "Phase 1F verification - synthetic in-flight cardiovascular examination.";
    const respiratory = "Phase 1F verification - synthetic in-flight respiratory examination.";
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const firstResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await steadyFill(page, "Cardiovascular Examination", cardiovascular);
    await page.getByRole("button", { name: "Save draft" }).click();
    const first = await firstRequest;
    const firstBody = JSON.parse(first.postData() ?? "{}") as { content?: unknown };
    expect(firstBody.content).toEqual({ cardiovascular_examination: cardiovascular });

    await steadyFill(page, "Respiratory Examination", respiratory);
    await expect(page.getByText(/Not saved/)).toBeVisible();
    await firstResponse;
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await expect(page.getByText(/Not saved/)).toBeVisible();

    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    const second = await secondRequest;
    const secondBody = JSON.parse(second.postData() ?? "{}") as { content?: unknown };
    expect(secondBody.content).toEqual({ respiratory_examination: respiratory });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});


test("persists, isolates, reloads, signs, and locks abdominal and neurological examination", async ({ page }) => {
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
  const patientA = await registerAndCheckIn(page, "Phase1G-A-" + suffix, "0770" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1G-B-" + suffix, "0771" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  const general = "Phase 1G verification - synthetic general examination.";
  const cardiovascular = "Phase 1G verification - synthetic cardiovascular examination.";
  const respiratory = "Phase 1G verification - synthetic respiratory examination.";
  const abdominal = "Phase 1G verification - synthetic abdominal gastrointestinal examination.";
  const neurological = "Phase 1G verification - synthetic neurological CNS examination.";

  await openHistory(page, patientA);
  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue("");

  const generalRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "General Examination", general);
  await page.getByRole("button", { name: "Save draft" }).click();
  const generalBody = JSON.parse((await generalRequest).postData() ?? "{}") as { content?: unknown };
  expect(generalBody.content).toEqual({ general_examination: general });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const systemsRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "Abdominal / Gastrointestinal Examination", abdominal);
  await steadyFill(page, "Neurological / CNS Examination", neurological);
  await page.getByRole("button", { name: "Save draft" }).click();
  const systemsBody = JSON.parse((await systemsRequest).postData() ?? "{}") as { content?: unknown };
  expect(systemsBody.content).toEqual({
    abdominal_examination: abdominal,
    neurological_examination: neurological,
  });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await steadyFill(page, "Cardiovascular Examination", cardiovascular);
  await steadyFill(page, "Respiratory Examination", respiratory);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(abdominal);
  await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(neurological);

  await page.reload();
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(abdominal);
  await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(neurological);

  await page.locator('nav a[href="/consultations"]').click();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const label of [
    "General Examination",
    "Cardiovascular Examination",
    "Respiratory Examination",
    "Abdominal / Gastrointestinal Examination",
    "Neurological / CNS Examination",
  ]) {
    await expect(page.getByLabel(label, { exact: true })).toHaveValue("");
  }

  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientB))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const testId of [
    "general-examination-read-only",
    "cardiovascular-examination-read-only",
    "respiratory-examination-read-only",
    "abdominal-examination-read-only",
    "neurological-examination-read-only",
  ]) {
    await expect(page.getByTestId(testId)).toHaveText("Not recorded.");
  }
  await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveCount(0);

  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(abdominal);
  await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(neurological);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientA))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const label of [
    "General Examination",
    "Cardiovascular Examination",
    "Respiratory Examination",
    "Abdominal / Gastrointestinal Examination",
    "Neurological / CNS Examination",
  ]) {
    await expect(page.getByLabel(label, { exact: true })).toHaveCount(0);
  }
  await expect(page.getByTestId("general-examination-read-only")).toHaveText(general);
  await expect(page.getByTestId("cardiovascular-examination-read-only")).toHaveText(cardiovascular);
  await expect(page.getByTestId("respiratory-examination-read-only")).toHaveText(respiratory);
  await expect(page.getByTestId("abdominal-examination-read-only")).toHaveText(abdominal);
  await expect(page.getByTestId("neurological-examination-read-only")).toHaveText(neurological);
  await expect(page.getByText("This Examination section is signed and immutable.")).toBeVisible();

  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});


test("rebases a stale neurological examination after a respiratory examination update", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1G-Rebase-" + suffix, "0772" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineRespiratory = "Phase 1G verification - synthetic baseline respiratory examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "Respiratory Examination", baselineRespiratory);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(baselineRespiratory);

    const updatedRespiratory = "Phase 1G verification - synthetic respiratory examination from writer A.";
    await steadyFill(page, "Respiratory Examination", updatedRespiratory);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    const updatedNeurological = "Phase 1G verification - synthetic neurological CNS examination from writer B.";
    await steadyFill(stalePage, "Neurological / CNS Examination", updatedNeurological);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const retry = await retryResponse;
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ neurological_examination: updatedNeurological });
    expect(retryBody.content).toEqual({ neurological_examination: updatedNeurological });
    expect(retry.request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();
    await expect(stalePage.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(updatedRespiratory);
    await expect(stalePage.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(updatedNeurological);

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(updatedRespiratory);
    await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(updatedNeurological);
  } finally {
    await stalePage.close();
  }
});


test("preserves same-field abdominal draft until explicit retry", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1G-SameField-" + suffix, "0773" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineAbdominal = "Phase 1G verification - synthetic baseline abdominal examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "Abdominal / Gastrointestinal Examination", baselineAbdominal);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(baselineAbdominal);

    const updatedAbdominalA = "Phase 1G verification - synthetic abdominal examination from writer A.";
    await steadyFill(page, "Abdominal / Gastrointestinal Examination", updatedAbdominalA);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    let nonAuthWrites = 0;
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() !== 401
      ) {
        nonAuthWrites += 1;
      }
    });
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const updatedAbdominalB = "Phase 1G verification - synthetic local abdominal examination.";
    await steadyFill(stalePage, "Abdominal / Gastrointestinal Examination", updatedAbdominalB);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    await stalePage.waitForTimeout(250);
    expect(nonAuthWrites).toBe(1);
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ abdominal_examination: updatedAbdominalB });
    await expect(stalePage.getByTestId("conflict-server-value-abdominal_examination")).toHaveText(updatedAbdominalA);
    await expect(stalePage.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(updatedAbdominalB);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const retry = await retryResponse;
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(retryBody.content).toEqual({ abdominal_examination: updatedAbdominalB });

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Abdominal / Gastrointestinal Examination", { exact: true })).toHaveValue(updatedAbdominalB);
  } finally {
    await stalePage.close();
  }
});


test("retains a neurological edit made while an abdominal save is in flight", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1G-InFlight-" + suffix, "0774" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  let delayFirstSave = true;
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  try {
    const abdominal = "Phase 1G verification - synthetic in-flight abdominal examination.";
    const neurological = "Phase 1G verification - synthetic in-flight neurological CNS examination.";
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const firstResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await steadyFill(page, "Abdominal / Gastrointestinal Examination", abdominal);
    await page.getByRole("button", { name: "Save draft" }).click();
    const first = await firstRequest;
    const firstBody = JSON.parse(first.postData() ?? "{}") as { content?: unknown };
    expect(firstBody.content).toEqual({ abdominal_examination: abdominal });

    await steadyFill(page, "Neurological / CNS Examination", neurological);
    await expect(page.getByText(/Not saved/)).toBeVisible();
    await firstResponse;
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await expect(page.getByText(/Not saved/)).toBeVisible();

    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    const second = await secondRequest;
    const secondBody = JSON.parse(second.postData() ?? "{}") as { content?: unknown };
    expect(secondBody.content).toEqual({ neurological_examination: neurological });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});


test("persists, isolates, reloads, signs, and locks genitourinary and musculoskeletal examination", async ({ page }) => {
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
  const patientA = await registerAndCheckIn(page, "Phase1H-A-" + suffix, "0770" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1H-B-" + suffix, "0771" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  const general = "Phase 1H verification - synthetic general examination.";
  const cardiovascular = "Phase 1H verification - synthetic cardiovascular examination.";
  const respiratory = "Phase 1H verification - synthetic respiratory examination.";
  const genitourinary = "Phase 1H verification - synthetic genitourinary gastrointestinal examination.";
  const musculoskeletal = "Phase 1H verification - synthetic musculoskeletal CNS examination.";

  await openHistory(page, patientA);
  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue("");

  const generalRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "General Examination", general);
  await page.getByRole("button", { name: "Save draft" }).click();
  const generalBody = JSON.parse((await generalRequest).postData() ?? "{}") as { content?: unknown };
  expect(generalBody.content).toEqual({ general_examination: general });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const systemsRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await steadyFill(page, "Genitourinary Examination", genitourinary);
  await steadyFill(page, "Musculoskeletal Examination", musculoskeletal);
  await page.getByRole("button", { name: "Save draft" }).click();
  const systemsBody = JSON.parse((await systemsRequest).postData() ?? "{}") as { content?: unknown };
  expect(systemsBody.content).toEqual({
    genitourinary_examination: genitourinary,
    musculoskeletal_examination: musculoskeletal,
  });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await steadyFill(page, "Cardiovascular Examination", cardiovascular);
  await steadyFill(page, "Respiratory Examination", respiratory);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(genitourinary);
  await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue(musculoskeletal);

  await page.reload();
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(genitourinary);
  await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue(musculoskeletal);

  await page.locator('nav a[href="/consultations"]').click();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const label of [
    "General Examination",
    "Cardiovascular Examination",
    "Respiratory Examination",
    "Genitourinary Examination",
    "Musculoskeletal Examination",
  ]) {
    await expect(page.getByLabel(label, { exact: true })).toHaveValue("");
  }

  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientB))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const testId of [
    "general-examination-read-only",
    "cardiovascular-examination-read-only",
    "respiratory-examination-read-only",
    "genitourinary-examination-read-only",
    "musculoskeletal-examination-read-only",
  ]) {
    await expect(page.getByTestId(testId)).toHaveText("Not recorded.");
  }
  await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveCount(0);

  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(general);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(cardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(respiratory);
  await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(genitourinary);
  await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue(musculoskeletal);

  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientA))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  for (const label of [
    "General Examination",
    "Cardiovascular Examination",
    "Respiratory Examination",
    "Genitourinary Examination",
    "Musculoskeletal Examination",
  ]) {
    await expect(page.getByLabel(label, { exact: true })).toHaveCount(0);
  }
  await expect(page.getByTestId("general-examination-read-only")).toHaveText(general);
  await expect(page.getByTestId("cardiovascular-examination-read-only")).toHaveText(cardiovascular);
  await expect(page.getByTestId("respiratory-examination-read-only")).toHaveText(respiratory);
  await expect(page.getByTestId("genitourinary-examination-read-only")).toHaveText(genitourinary);
  await expect(page.getByTestId("musculoskeletal-examination-read-only")).toHaveText(musculoskeletal);
  await expect(page.getByText("This Examination section is signed and immutable.")).toBeVisible();

  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});




test("rebases a stale musculoskeletal examination after a neurological examination update", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1H-Rebase-" + suffix, "0772" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineNeurological = "Phase 1H verification - synthetic baseline neurological examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "Neurological / CNS Examination", baselineNeurological);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(baselineNeurological);

    const updatedNeurological = "Phase 1H verification - synthetic neurological examination from writer A.";
    await steadyFill(page, "Neurological / CNS Examination", updatedNeurological);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    const updatedMusculoskeletal = "Phase 1H verification - synthetic musculoskeletal CNS examination from writer B.";
    await steadyFill(stalePage, "Musculoskeletal Examination", updatedMusculoskeletal);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const retry = await retryResponse;
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ musculoskeletal_examination: updatedMusculoskeletal });
    expect(retryBody.content).toEqual({ musculoskeletal_examination: updatedMusculoskeletal });
    expect(retry.request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();
    await expect(stalePage.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(updatedNeurological);
    await expect(stalePage.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue(updatedMusculoskeletal);

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Neurological / CNS Examination", { exact: true })).toHaveValue(updatedNeurological);
    await expect(page.getByLabel("Musculoskeletal Examination", { exact: true })).toHaveValue(updatedMusculoskeletal);
  } finally {
    await stalePage.close();
  }
});




test("preserves same-field genitourinary draft until explicit retry", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1H-SameField-" + suffix, "0773" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baselineAbdominal = "Phase 1H verification - synthetic baseline genitourinary examination.";
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await steadyFill(page, "Genitourinary Examination", baselineAbdominal);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(baselineAbdominal);

    const updatedAbdominalA = "Phase 1H verification - synthetic genitourinary examination from writer A.";
    await steadyFill(page, "Genitourinary Examination", updatedAbdominalA);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    let nonAuthWrites = 0;
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() !== 401
      ) {
        nonAuthWrites += 1;
      }
    });
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const updatedAbdominalB = "Phase 1H verification - synthetic local genitourinary examination.";
    await steadyFill(stalePage, "Genitourinary Examination", updatedAbdominalB);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    await stalePage.waitForTimeout(250);
    expect(nonAuthWrites).toBe(1);
    const conflictBody = JSON.parse(conflict.request().postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ genitourinary_examination: updatedAbdominalB });
    await expect(stalePage.getByTestId("conflict-server-value-genitourinary_examination")).toHaveText(updatedAbdominalA);
    await expect(stalePage.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(updatedAbdominalB);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const retry = await retryResponse;
    const retryBody = JSON.parse(retry.request().postData() ?? "{}") as { content?: unknown };
    expect(retryBody.content).toEqual({ genitourinary_examination: updatedAbdominalB });

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Genitourinary Examination", { exact: true })).toHaveValue(updatedAbdominalB);
  } finally {
    await stalePage.close();
  }
});




test("retains a musculoskeletal edit made while an genitourinary save is in flight", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1H-InFlight-" + suffix, "0774" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  let delayFirstSave = true;
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  try {
    const genitourinary = "Phase 1H verification - synthetic in-flight genitourinary examination.";
    const musculoskeletal = "Phase 1H verification - synthetic in-flight musculoskeletal CNS examination.";
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const firstResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await steadyFill(page, "Genitourinary Examination", genitourinary);
    await page.getByRole("button", { name: "Save draft" }).click();
    const first = await firstRequest;
    const firstBody = JSON.parse(first.postData() ?? "{}") as { content?: unknown };
    expect(firstBody.content).toEqual({ genitourinary_examination: genitourinary });

    await steadyFill(page, "Musculoskeletal Examination", musculoskeletal);
    await expect(page.getByText(/Not saved/)).toBeVisible();
    await firstResponse;
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
    await expect(page.getByText(/Not saved/)).toBeVisible();

    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    const second = await secondRequest;
    const secondBody = JSON.parse(second.postData() ?? "{}") as { content?: unknown };
    expect(secondBody.content).toEqual({ musculoskeletal_examination: musculoskeletal });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});




test("preserves genitourinary and musculoskeletal drafts and requires explicit retry after a stale sign", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1H-StaleSign-" + suffix, "0745" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  await ensureSyntheticComplaint(page);
  const baselineFamily = "Phase 1H synthetic sign baseline family";
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
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    const updatedGenitourinary = "Phase 1H synthetic writer A genitourinary examination";
    await steadyFill(page, "Genitourinary Examination", updatedGenitourinary);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    const localMusculoskeletal = "Phase 1H synthetic local musculoskeletal examination";
    await steadyFill(stalePage, "Musculoskeletal Examination", localMusculoskeletal);
    await stalePage.getByRole("tab", { name: "Notes", exact: true }).click();
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
    await expect(stalePage.getByRole("alert").filter({ hasText: "This consultation changed" })).toContainText("Genitourinary examination");
    expect(signResponses).toBe(1);
    const conflictBody = JSON.parse((await conflict.request().postData()) ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ musculoskeletal_examination: localMusculoskeletal });
    expect(conflict.request().headers()["if-match"]).toBeTruthy();
    expect(conflict.headers()["etag"]).toBeTruthy();
    await expect(stalePage.getByTestId("conflict-server-value-genitourinary_examination")).toHaveText(updatedGenitourinary);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("Genitourinary Examination")).toHaveValue(updatedGenitourinary);
    await expect(stalePage.getByLabel("Musculoskeletal Examination")).toHaveValue(localMusculoskeletal);
    await stalePage.getByRole("tab", { name: "Notes", exact: true }).click();
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
    expect(signedBody.content?.genitourinary_examination).toBe(updatedGenitourinary);
    expect(signedBody.content?.musculoskeletal_examination).toBe(localMusculoskeletal);
    await expect(stalePage.getByText("This consultation is signed and immutable.")).toBeVisible();
  } finally {
    await stalePage.close();
  }
});


const PHASE_1I_CARDIO_NORMAL = "Cardiovascular examination: no abnormal findings noted.";
const PHASE_1I_RESPIRATORY_NORMAL = "Respiratory examination: no abnormal findings noted.";
const PHASE_1I_GENERAL_NORMAL = "Patient appears clinically well. No abnormal general findings noted.";

test("inserts only explicitly selected reviewed normal findings as an editable unsaved draft", async ({ page }) => {
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
  const patientName = await registerAndCheckIn(page, "Phase1I-Insert-" + suffix, "0780" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  const panel = page.getByTestId("reviewed-normal-panel");
  await expect(panel).toBeVisible();
  for (const label of [
    "General",
    "Cardiovascular",
    "Respiratory",
    "Abdominal / Gastrointestinal",
    "Neurological / CNS",
    "Genitourinary",
    "Musculoskeletal",
  ]) {
    const checkbox = page.getByLabel(label, { exact: true });
    await expect(checkbox).toHaveCount(1);
    await expect(checkbox).not.toBeChecked();
  }
  const insertButton = page.getByRole("button", { name: "Insert selected findings", exact: true });
  await expect(insertButton).toBeDisabled();

  let noteMutationRequests = 0;
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      ((request.url().endsWith("/notes/") && request.method() === "PATCH") ||
        (request.url().endsWith("/sign/") && request.method() === "POST"))
    ) {
      noteMutationRequests += 1;
    }
  });

  await page.getByLabel("Cardiovascular", { exact: true }).check();
  await page.getByLabel("Respiratory", { exact: true }).check();
  await expect(insertButton).toBeEnabled();
  await insertButton.click();
  await expect(panel).toHaveCount(0);
  await page.waitForTimeout(250);
  expect(noteMutationRequests).toBe(0);
  await expect(page.getByText(/Not saved/)).toBeVisible();
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(PHASE_1I_RESPIRATORY_NORMAL);
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue("");

  const editedCardiovascular = "Phase 1I verification - synthetic edited cardiovascular finding.";
  await steadyFill(page, "Cardiovascular Examination", editedCardiovascular);
  const saveRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  const saveResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  const savedBody = JSON.parse((await saveRequest).postData() ?? "{}") as { content?: unknown };
  expect(savedBody.content).toEqual({
    cardiovascular_examination: editedCardiovascular,
    respiratory_examination: PHASE_1I_RESPIRATORY_NORMAL,
  });
  await saveResponse;
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.reload();
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(editedCardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(PHASE_1I_RESPIRATORY_NORMAL);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("protects existing and locally dirty examination text from reviewed-normal insertion", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1I-Protect-" + suffix, "0781" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  const existingCardiovascular = "Phase 1I verification - synthetic existing cardiovascular documentation.";
  const localRespiratory = "Phase 1I verification - synthetic unsaved respiratory documentation.";
  await steadyFill(page, "Cardiovascular Examination", existingCardiovascular);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  await steadyFill(page, "Respiratory Examination", localRespiratory);

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular", { exact: true })).toBeDisabled();
  await expect(page.getByLabel("Respiratory", { exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /select all|all normal|mark all/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Insert selected findings", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByTestId("reviewed-normal-panel")).toHaveCount(0);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(existingCardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(localRespiratory);

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular", { exact: true })).not.toBeChecked();
  await expect(page.getByLabel("Respiratory", { exact: true })).not.toBeChecked();
  await page.getByLabel("General", { exact: true }).check();
  await page.getByRole("button", { name: "Insert selected findings", exact: true }).click();
  await expect(page.getByLabel("General Examination", { exact: true })).toHaveValue(PHASE_1I_GENERAL_NORMAL);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(existingCardiovascular);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(localRespiratory);

  const saveRequest = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  const savedBody = JSON.parse((await saveRequest).postData() ?? "{}") as { content?: unknown };
  expect(savedBody.content).toMatchObject({
    general_examination: PHASE_1I_GENERAL_NORMAL,
  });
  if (
    savedBody.content &&
    typeof savedBody.content === "object" &&
    "respiratory_examination" in savedBody.content
  ) {
    expect(savedBody.content).toMatchObject({
      respiratory_examination: localRespiratory,
    });
  }
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();
});

test("closes and clears reviewed-normal state across sections and patients without leaking drafts", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1I-IsolationA-" + suffix, "0782" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1I-IsolationB-" + suffix, "0783" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);
  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  await page.getByLabel("Cardiovascular", { exact: true }).check();
  await page.getByRole("button", { name: "Insert selected findings", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  await page.getByLabel("Respiratory", { exact: true }).check();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByTestId("reviewed-normal-panel")).toHaveCount(0);
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");

  await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
  await page.getByLabel("Respiratory", { exact: true }).check();
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await expect(page.getByTestId("reviewed-normal-panel")).toHaveCount(0);
  await openHistory(page, patientB);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");

  await openHistory(page, patientA);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
  await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue("");
  const persistedState = await page.evaluate(() => Object.values(localStorage).concat(Object.values(sessionStorage)).join("\n"));
  expect(persistedState).not.toContain(PHASE_1I_CARDIO_NORMAL);
});

test("handles same-field stale conflicts for a template-inserted examination field", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1I-SameField-" + suffix, "0784" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();

    const serverCardiovascular = "Phase 1I verification - synthetic server cardiovascular documentation.";
    await steadyFill(page, "Cardiovascular Examination", serverCardiovascular);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
    await stalePage.getByLabel("Cardiovascular", { exact: true }).check();
    await stalePage.getByRole("button", { name: "Insert selected findings", exact: true }).click();
    await expect(stalePage.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const conflictRequest = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const conflict = await conflictResponse;
    const conflictBody = JSON.parse((await conflictRequest).postData() ?? "{}") as { content?: unknown };
    expect(conflictBody.content).toEqual({ cardiovascular_examination: PHASE_1I_CARDIO_NORMAL });
    await expect(stalePage.getByTestId("conflict-server-value-cardiovascular_examination")).toHaveText(serverCardiovascular);
    await expect(stalePage.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    const retryRequest = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const retry = await retryResponse;
    const retryBody = JSON.parse((await retryRequest).postData() ?? "{}") as { content?: unknown };
    expect(retryBody.content).toEqual({ cardiovascular_examination: PHASE_1I_CARDIO_NORMAL });
    expect(retry.request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
  } finally {
    await stalePage.close();
  }
});

test("rebases a template-inserted field after a non-overlapping examination update", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1I-Rebase-" + suffix, "0785" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();

    const serverCardiovascular = "Phase 1I verification - synthetic rebase cardiovascular documentation.";
    await steadyFill(page, "Cardiovascular Examination", serverCardiovascular);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
    await stalePage.getByLabel("Respiratory", { exact: true }).check();
    await stalePage.getByRole("button", { name: "Insert selected findings", exact: true }).click();

    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    const staleRequest = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await stalePage.getByRole("button", { name: "Save draft", exact: true }).click();
    const conflict = await conflictResponse;
    const retry = await retryResponse;
    const staleBody = JSON.parse((await staleRequest).postData() ?? "{}") as { content?: unknown };
    expect(staleBody.content).toEqual({ respiratory_examination: PHASE_1I_RESPIRATORY_NORMAL });
    const retryBody = JSON.parse((await retry).request().postData() ?? "{}") as { content?: unknown };
    expect(retryBody.content).toEqual({ respiratory_examination: PHASE_1I_RESPIRATORY_NORMAL });
    expect((await retry).request().headers()["if-match"]).toBe(conflict.headers()["etag"]);
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();
    await expect(stalePage.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(serverCardiovascular);
    await expect(stalePage.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(PHASE_1I_RESPIRATORY_NORMAL);

    await page.reload();
    await openHistory(page, patientName);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(serverCardiovascular);
    await expect(page.getByLabel("Respiratory Examination", { exact: true })).toHaveValue(PHASE_1I_RESPIRATORY_NORMAL);
  } finally {
    await stalePage.close();
  }
});

test("reviewed-normal quick action is unavailable after signing", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1I-Signed-" + suffix, "0786" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await ensureSyntheticComplaint(page);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByRole("button", { name: "Sign consultation" }).click();
  await page.getByRole("button", { name: "Confirm signature" }).click();
  await expect(page.getByText(new RegExp("Consultation signed for " + patientName))).toBeVisible();
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  await expect(page.getByRole("button", { name: "Insert reviewed normal findings", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("reviewed-normal-panel")).toHaveCount(0);
  await expect(page.getByLabel("Cardiovascular", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("cardiovascular-examination-read-only")).toHaveText("Not recorded.");
  await expect(page.getByText("This Examination section is signed and immutable.")).toBeVisible();
});

test("retains a reviewed-normal insertion made while another examination save is in flight", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1I-InFlight-" + suffix, "0787" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  let delayFirstSave = true;
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  try {
    const manualGeneral = "Phase 1I verification - synthetic in-flight general examination.";
    await steadyFill(page, "General Examination", manualGeneral);
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const firstResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    await firstRequest;
    await page.getByRole("button", { name: "Insert reviewed normal findings", exact: true }).click();
    await page.getByLabel("Cardiovascular", { exact: true }).check();
    await page.getByRole("button", { name: "Insert selected findings", exact: true }).click();
    await expect(page.getByLabel("Cardiovascular Examination", { exact: true })).toHaveValue(PHASE_1I_CARDIO_NORMAL);
    await expect(page.getByText(/Not saved/)).toBeVisible();
    await firstResponse;
    await expect(page.getByText(/Not saved/)).toBeVisible();

    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    const secondBody = JSON.parse((await secondRequest).postData() ?? "{}") as { content?: unknown };
    expect(secondBody.content).toEqual({ cardiovascular_examination: PHASE_1I_CARDIO_NORMAL });
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});
test("Phase 1J debounces edits, sends dirty-only autosave, and shows persisted saved time", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-Debounce-" + suffix, "0780" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const firstValue = "Phase 1J verification — first synthetic HPI";
  const finalValue = "Phase 1J verification — final synthetic HPI";
  const noteRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      noteRequests.push(request.headers()["x-klinklik-autosave"] ?? "manual");
    }
  });

  const autosaveRequestPromise = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  const autosaveResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await steadyFill(page, "History of present illness (HPI)", firstValue);
  await page.waitForTimeout(1800);
  expect(noteRequests).toHaveLength(0);

  await steadyFill(page, "History of present illness (HPI)", finalValue);
  await page.waitForTimeout(1800);
  expect(noteRequests).toHaveLength(0);

  const request = await autosaveRequestPromise;
  expect(request.headers()["x-klinklik-autosave"]).toBe("1");
  const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown };
  expect(body.content).toEqual({ hpi: finalValue });
  const response = await autosaveResponsePromise;
  const responseBody = await response.json() as { saved_at?: string };
  expect(responseBody.saved_at).toBeTruthy();
  await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  await expect(page.getByText("Consultation draft autosaved.")).toBeVisible();

  const browserStorage = await page.evaluate(() => JSON.stringify({
    local: { ...localStorage },
    session: { ...sessionStorage },
  }));
  expect(browserStorage).not.toContain(finalValue);
});

test("Phase 1J manual Save cancels the debounce and does not duplicate the request", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-Manual-" + suffix, "0781" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const value = "Phase 1J verification — manual synthetic HPI";
  const noteRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      noteRequests.push(request.headers()["x-klinklik-autosave"] ?? "manual");
    }
  });
  await steadyFill(page, "History of present illness (HPI)", value);
  const requestPromise = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  const request = await requestPromise;
  expect(request.headers()["x-klinklik-autosave"]).toBeUndefined();
  expect(JSON.parse(request.postData() ?? "{}")).toEqual({ content: { hpi: value } });
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();
  await page.waitForTimeout(3500);
  expect(noteRequests).toHaveLength(1);
  await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
});

test("Phase 1J preserves edits during an in-flight autosave without overlap", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-InFlight-" + suffix, "0782" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();

  let delayFirstSave = true;
  let inFlight = 0;
  let maximumInFlight = 0;
  const noteRequests: Array<{ body: Record<string, unknown>; autosave: string | undefined }> = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      inFlight += 1;
      maximumInFlight = Math.max(maximumInFlight, inFlight);
      noteRequests.push({
        body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>,
        autosave: request.headers()["x-klinklik-autosave"],
      });
    }
  });
  page.on("response", (response) => {
    if (
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH"
    ) {
      inFlight = Math.max(0, inFlight - 1);
    }
  });
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && delayFirstSave) {
      delayFirstSave = false;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    await route.continue();
  });

  try {
    const firstValue = "Phase 1J verification — synthetic cardiovascular autosave";
    const secondValue = "Phase 1J verification — synthetic respiratory follow-up";
    const firstRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await steadyFill(page, "Cardiovascular Examination", firstValue);
    await firstRequest;
    const secondRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await steadyFill(page, "Respiratory Examination", secondValue);
    await page.waitForTimeout(1500);
    expect(noteRequests).toHaveLength(1);
    await expect(page.getByText(/Not saved/)).toBeVisible();

    await secondRequest;
    expect(noteRequests).toHaveLength(2);
    expect(noteRequests[0].body.content).toEqual({ cardiovascular_examination: firstValue });
    expect(noteRequests[0].autosave).toBe("1");
    expect(noteRequests[1].body.content).toEqual({ respiratory_examination: secondValue });
    expect(noteRequests[1].autosave).toBe("1");
    expect(maximumInFlight).toBe(1);
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});
test("Phase 1K preserves Phase 1J true same-field conflict blocking until explicit Save", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-SameField-" + suffix, "0783" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baseline = "Phase 1J verification — synthetic baseline HPI";
  await steadyFill(page, "History of present illness (HPI)", baseline);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);

    const serverValue = "Phase 1J verification — synthetic server HPI";
    await steadyFill(page, "History of present illness (HPI)", serverValue);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    const requestMarkers: string[] = [];
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() !== 401
      ) {
        requestMarkers.push(response.request().headers()["x-klinklik-autosave"] ?? "manual");
      }
    });
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const localValue = "Phase 1J verification — synthetic local conflict HPI";
    await steadyFill(stalePage, "History of present illness (HPI)", localValue);
    const conflict = await conflictResponse;
    expect(requestMarkers).toEqual(["1"]);
    expect(JSON.parse(conflict.request().postData() ?? "{}")).toEqual({ content: { hpi: localValue } });
    await expect(stalePage.getByTestId("conflict-server-value-hpi")).toHaveText(serverValue);
    await expect(stalePage.getByText(/Not saved/)).toBeVisible();

    await stalePage.waitForTimeout(3500);
    expect(requestMarkers).toEqual(["1"]);

    const explicitRequestPromise = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const explicitResponsePromise = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const explicitRequest = await explicitRequestPromise;
    const explicitResponse = await explicitResponsePromise;
    expect(explicitRequest.headers()["x-klinklik-autosave"]).toBeUndefined();
    expect(JSON.parse(explicitRequest.postData() ?? "{}")).toEqual({ content: { hpi: localValue } });
    expect(explicitResponse.status()).toBe(200);
    await expect(stalePage.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();

    const resumedRequestPromise = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    const resumedValue = "Phase 1J verification — synthetic resumed autosave HPI";
    await steadyFill(stalePage, "History of present illness (HPI)", resumedValue);
    const resumedRequest = await resumedRequestPromise;
    expect(resumedRequest.headers()["x-klinklik-autosave"]).toBe("1");
    expect(JSON.parse(resumedRequest.postData() ?? "{}")).toEqual({ content: { hpi: resumedValue } });
  } finally {
    await stalePage.close();
  }
});

test("Phase 1J rebases a non-overlapping stale autosave and retries once safely", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-Rebase-" + suffix, "0784" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const baseline = "Phase 1J verification — synthetic baseline HPI for rebase";
  await steadyFill(page, "History of present illness (HPI)", baseline);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Consultation draft saved.")).toBeVisible();

  const stalePage = await page.context().newPage();
  try {
    await stalePage.goto("/consultations");
    await expect(stalePage.locator('nav a[href="/consultations"]')).toBeVisible();
    await openHistory(stalePage, patientName);

    const serverHpi = "Phase 1J verification — synthetic server HPI for rebase";
    await steadyFill(page, "History of present illness (HPI)", serverHpi);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Consultation draft saved.")).toBeVisible();

    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    const localGeneral = "Phase 1J verification — synthetic non-overlapping general examination";
    const requests: Array<{ content?: unknown; autosave?: string }> = [];
    stalePage.on("response", (response) => {
      if (
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() !== 401
      ) {
        const request = response.request();
        const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown };
        requests.push({ content: body.content, autosave: request.headers()["x-klinklik-autosave"] });
      }
    });
    const conflictResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    const retryResponse = stalePage.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await steadyFill(stalePage, "General Examination", localGeneral);
    await conflictResponse;
    await retryResponse;
    expect(requests).toEqual([
      { content: { general_examination: localGeneral }, autosave: "1" },
      { content: { general_examination: localGeneral }, autosave: "1" },
    ]);
    await expect(stalePage.getByText("Consultation draft autosaved.")).toBeVisible();

    await stalePage.getByRole("tab", { name: "History", exact: true }).click();
    await expect(stalePage.getByLabel("History of present illness (HPI)")).toHaveValue(serverHpi);
    await stalePage.getByRole("tab", { name: "Examination", exact: true }).click();
    await expect(stalePage.getByLabel("General Examination")).toHaveValue(localGeneral);
  } finally {
    await stalePage.close();
  }
});
test("Phase 1K patient switch confirmation preserves or discards local draft safely", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1K-SwitchA-" + suffix, "0794" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1K-SwitchB-" + suffix, "0795" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);
  await openHistory(page, patientA);

  const abandonedValue = "Phase 1K verification — synthetic patient A unsaved draft";
  const noteRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      noteRequests.push(request.url());
    }
  });
  await steadyFill(page, "History of present illness (HPI)", abandonedValue);
  await page.waitForTimeout(700);

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toBe("This consultation has unsaved changes. Leave and discard them?");
    await dialog.dismiss();
  });
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue(abandonedValue);

  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toBe("This consultation has unsaved changes. Leave and discard them?");
    await dialog.accept();
  });
  await page.getByRole("listitem").filter({ hasText: patientB }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue("");
  await page.waitForTimeout(3500);
  expect(noteRequests).toHaveLength(0);

  await page.getByRole("listitem").filter({ hasText: patientA }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Start encounter" }).click();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue("");
});
test("Phase 1K-F ignores a late Start Encounter response from the previous patient session", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientA = await registerAndCheckIn(page, "Phase1K-F-RaceA-" + suffix, "0796" + suffix);
  const patientB = await registerAndCheckIn(page, "Phase1K-F-RaceB-" + suffix, "0797" + suffix);
  await triageFromQueue(page, patientA);
  await triageFromQueue(page, patientB);

  await page.locator('nav a[href="/consultations"]').click();
  await expect(page).toHaveURL(/\/consultations$/);
  await page.getByRole("listitem").filter({ hasText: patientA }).click();
  await page.getByRole("tab", { name: "History", exact: true }).click();

  let releasePatientA: (() => void) | undefined;
  const patientAResponseGate = new Promise<void>((resolve) => {
    releasePatientA = resolve;
  });
  let delayFirstStart = true;
  await page.route("**/api/v1/clinic/encounters/", async (route) => {
    if (route.request().method() === "POST" && delayFirstStart) {
      delayFirstStart = false;
      await patientAResponseGate;
    }
    await route.continue();
  });

  try {
    const patientARequest = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/v1/clinic/encounters/") &&
        request.method() === "POST",
    );
    const patientAResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/clinic/encounters/") &&
        response.request().method() === "POST" &&
        response.status() === 201,
    );
    await page.getByRole("button", { name: "Start encounter" }).click();
    await patientARequest;

    await page.getByRole("listitem").filter({ hasText: patientB }).click();
    await expect(page.getByLabel("Patient and encounter context")).toContainText(patientB);
    await expect(page.getByRole("button", { name: "Save draft" })).toHaveCount(0);

    releasePatientA?.();
    expect((await patientAResponse).status()).toBe(201);
    await expect(page.getByLabel("Patient and encounter context")).toContainText(patientB);
    await expect(page.getByRole("button", { name: "Start encounter" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save draft" })).toHaveCount(0);
    await expect(page.getByLabel("History of present illness (HPI)")).toHaveCount(0);

    const patientBResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/clinic/encounters/") &&
        response.request().method() === "POST" &&
        response.status() === 201,
    );
    await page.getByRole("button", { name: "Start encounter" }).click();
    expect((await patientBResponse).status()).toBe(201);
    await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Notes", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(page.getByLabel("History of present illness (HPI)")).toHaveValue("");
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/");
  }
});
test("Phase 1J keeps section switching, reviewed-normal insertion, and debounce state intact", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1J-Sections-" + suffix, "0787" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const noteRequests: Array<{ content?: unknown; autosave?: string }> = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      const body = JSON.parse(request.postData() ?? "{}") as { content?: unknown };
      noteRequests.push({ content: body.content, autosave: request.headers()["x-klinklik-autosave"] });
    }
  });

  const hpi = "Phase 1J verification — synthetic section-switch HPI";
  const hpiRequestPromise = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  const hpiResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await steadyFill(page, "History of present illness (HPI)", hpi);
  await page.getByRole("tab", { name: "Examination", exact: true }).click();
  const hpiRequest = await hpiRequestPromise;
  await hpiResponsePromise;
  expect(JSON.parse(hpiRequest.postData() ?? "{}")).toEqual({ content: { hpi } });
  expect(hpiRequest.headers()["x-klinklik-autosave"]).toBe("1");
  expect(noteRequests).toHaveLength(1);

  await page.getByRole("button", { name: "Insert reviewed normal findings" }).click();
  await page.getByLabel("Cardiovascular", { exact: true }).check();
  const reviewedRequestPromise = page.waitForRequest(
    (request) =>
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH",
  );
  const reviewedResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await page.getByRole("button", { name: "Insert selected findings" }).click();
  await page.waitForTimeout(500);
  expect(noteRequests).toHaveLength(1);
  const reviewedRequest = await reviewedRequestPromise;
  const reviewedResponse = await reviewedResponsePromise;
  expect(reviewedRequest.headers()["x-klinklik-autosave"]).toBe("1");
  expect(JSON.parse(reviewedRequest.postData() ?? "{}")).toEqual({
    content: { cardiovascular_examination: "Cardiovascular examination: no abnormal findings noted." },
  });
  expect(reviewedResponse.status()).toBe(200);
  await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
});

test("Phase 1K retries transient autosave failures with current dirty fields", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1K-Retry-" + suffix, "0790" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  const firstHpi = "Phase 1K verification — synthetic first failed HPI";
  const currentHpi = "Phase 1K verification — synthetic current HPI";
  const currentGeneral = "Phase 1K verification — synthetic current general examination";
  const requests: Array<{
    body: Record<string, unknown>;
    etag: string | undefined;
    autosave: string | undefined;
  }> = [];
  let inFlight = 0;
  let maximumInFlight = 0;
  let failFirstRequest = true;

  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      inFlight += 1;
      maximumInFlight = Math.max(maximumInFlight, inFlight);
      requests.push({
        body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>,
        etag: request.headers()["if-match"],
        autosave: request.headers()["x-klinklik-autosave"],
      });
    }
  });
  page.on("response", (response) => {
    if (
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH"
    ) {
      inFlight = Math.max(0, inFlight - 1);
    }
  });

  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && failFirstRequest) {
      failFirstRequest = false;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic local transient failure" }),
      });
      return;
    }
    await route.continue();
  });

  try {
    const firstFailure = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 503,
    );
    await steadyFill(page, "History of present illness (HPI)", firstHpi);
    await firstFailure;
    await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
    await page.waitForTimeout(500);
    expect(requests).toHaveLength(1);

    const retrySuccess = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await steadyFill(page, "History of present illness (HPI)", currentHpi);
    await page.getByRole("tab", { name: "Examination", exact: true }).click();
    await steadyFill(page, "General Examination", currentGeneral);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await retrySuccess;

    expect(requests).toHaveLength(2);
    expect(requests[0].body.content).toEqual({ hpi: firstHpi });
    expect(requests[1].body.content).toEqual({ hpi: currentHpi, general_examination: currentGeneral });
    expect(requests[0].autosave).toBe("1");
    expect(requests[1].autosave).toBe("1");
    expect(requests[0].etag).toBeTruthy();
    expect(requests[1].etag).toBe(requests[0].etag);
    expect(maximumInFlight).toBe(1);
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});

test("Phase 1K manual Save cancels the pending retry timer", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1K-Manual-" + suffix, "0791" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  let failFirstRequest = true;
  const requestMarkers: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      requestMarkers.push(request.headers()["x-klinklik-autosave"] ?? "manual");
    }
  });
  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && failFirstRequest) {
      failFirstRequest = false;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic local transient failure" }),
      });
      return;
    }
    await route.continue();
  });

  try {
    const firstFailure = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 503,
    );
    await steadyFill(page, "History of present illness (HPI)", "Phase 1K verification — synthetic manual retry");
    await firstFailure;
    await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();

    const manualResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 200,
    );
    await page.getByRole("button", { name: "Save draft" }).click();
    await manualResponse;
    await page.waitForTimeout(2500);
    expect(requestMarkers).toEqual(["1", "manual"]);
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});

test("Phase 1K suppresses autosave while offline, retries online, and protects unload", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1K-Online-" + suffix, "0792" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  let noteRequests = 0;
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      noteRequests += 1;
    }
  });

  await steadyFill(page, "History of present illness (HPI)", "Phase 1K verification — synthetic offline draft");
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();
  await page.waitForTimeout(3500);
  expect(noteRequests).toBe(0);

  const blockedUnload = await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(blockedUnload).toBe(true);

  const retryResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/clinic/encounters/") &&
      response.url().endsWith("/notes/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await retryResponse;
  await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();

  const cleanUnload = await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(cleanUnload).toBe(false);
});

test("Phase 1K reconciles a lost autosave response without a false conflict", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const patientName = await registerAndCheckIn(page, "Phase1K-Lost-" + suffix, "0793" + suffix);
  await triageFromQueue(page, patientName);
  await openHistory(page, patientName);

  let firstRequest = true;
  const requests: Array<{ body: Record<string, unknown>; etag: string | undefined }> = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/v1/clinic/encounters/") &&
      request.url().endsWith("/notes/") &&
      request.method() === "PATCH"
    ) {
      requests.push({
        body: JSON.parse(request.postData() ?? "{}") as Record<string, unknown>,
        etag: request.headers()["if-match"],
      });
    }
  });

  await page.route("**/api/v1/clinic/encounters/*/notes/", async (route) => {
    if (route.request().method() === "PATCH" && firstRequest) {
      firstRequest = false;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  try {
    const firstRequestObserved = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "PATCH",
    );
    await steadyFill(page, "History of present illness (HPI)", "Phase 1K verification — synthetic lost-response HPI");
    await firstRequestObserved;
    await expect(page.getByText("Not saved — retrying", { exact: true })).toBeVisible();

    const reconciliation = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/clinic/encounters/") &&
        response.url().endsWith("/notes/") &&
        response.request().method() === "PATCH" &&
        response.status() === 412,
    );
    await reconciliation;
    expect(requests).toHaveLength(2);
    expect(requests[1].body.content).toEqual(requests[0].body.content);
    expect(requests[1].etag).toBe(requests[0].etag);
    await expect(page.getByText(/^Saved \d{2}:\d{2}:\d{2}$/)).toBeVisible();
    await expect(page.getByText("Latest saved values from another update")).toHaveCount(0);
    await expect(page.getByText(/Not saved/)).toHaveCount(0);
  } finally {
    await page.unroute("**/api/v1/clinic/encounters/*/notes/");
  }
});
