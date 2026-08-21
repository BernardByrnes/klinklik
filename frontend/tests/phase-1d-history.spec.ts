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
  await page.getByRole("tab", { name: "History", exact: true }).click();
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

    const socialRequest = stalePage.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/clinic/encounters/") &&
        request.url().endsWith("/notes/") &&
        request.method() === "POST",
    );
    await steadyFill(stalePage, "Relevant Social History", updatedSocial);
    await stalePage.getByRole("button", { name: "Save draft" }).click();
    const socialBody = JSON.parse((await socialRequest).postData() ?? "{}") as { content?: unknown };
    expect(socialBody.content).toEqual({ social_history: updatedSocial });
    await expect(stalePage.getByText("Consultation draft saved.")).toBeVisible();

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
