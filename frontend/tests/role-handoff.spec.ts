import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const REVIEW_DIR = "K:\\clinicopus\\artifacts\\design-review";
const ROLE_PASSWORD = "ClinicopusDemo123!";
const DEMO_PASSWORD = "ClinicopusDemo!2026";

/*
 * Controlled inputs can be reset once by React hydration; refill until the
 * values stick, then submit.
 */
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
  throw new Error(`Input "${label}" did not hold value "${value}" (hydration race)`);
}

async function login(page: Page, username: string, password = ROLE_PASSWORD) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("role handoffs across independent sessions: reception → nurse → doctor → cashier", async ({ browser }) => {
  fs.mkdirSync(REVIEW_DIR, { recursive: true });
  const suffix = Date.now().toString().slice(-6);
  const patientName = `Handoff Patient${suffix}`;

  // --- Reception: register, check in, and leave an unpaid invoice for the cashier.
  const receptionContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const receptionPage = await receptionContext.newPage();
  await login(receptionPage, "reception@clinicopus.local");
  await expect(receptionPage).toHaveURL(/\/overview$/);

  // Role-aware navigation: reception must not see Triage or Consultations.
  await expect(receptionPage.getByRole("link", { name: "Triage" })).toHaveCount(0);
  await expect(receptionPage.getByRole("link", { name: "Consultations" })).toHaveCount(0);

  await receptionPage.locator('nav a[href="/patients"]').click();
  await steadyFill(receptionPage, "First name", "Handoff");
  await steadyFill(receptionPage, "Last name", `Patient${suffix}`);
  await steadyFill(receptionPage, "Phone", "0711" + suffix);
  await receptionPage.locator("form").getByRole("button", { name: "Register patient" }).click();
  await expect(receptionPage.getByText(new RegExp("registered as P-"))).toBeVisible();
  await receptionPage.getByRole("button", { name: "Check in patient" }).click();
  await expect(receptionPage.getByText(/checked in as/)).toBeVisible();

  // Reception issues the invoice; the cashier will collect it from a fresh session.
  await receptionPage.locator('nav a[href="/billing"]').click();
  await expect(receptionPage).toHaveURL(/\/billing$/);
  await steadyFill(receptionPage, "Patient", `Patient${suffix}`);
  await receptionPage.getByRole("option", { name: new RegExp(patientName) }).click();
  await expect(receptionPage.getByText(new RegExp(patientName + " · P-"))).toBeVisible();
  await receptionPage.getByRole("button", { name: "Create invoice" }).click();
  await expect(receptionPage.getByText(new RegExp("Invoice INV-\\S+ created for " + patientName))).toBeVisible();
  const storageKeys = await receptionPage.evaluate(() => ({
    local: Object.keys(window.localStorage),
    session: Object.keys(window.sessionStorage),
  }));
  const tokenStored = [...storageKeys.local, ...storageKeys.session].some((key) => /token|access|refresh/i.test(key));
  expect(tokenStored, "access token must stay out of web storage").toBe(false);

  await receptionPage.reload();
  await expect(receptionPage.getByRole("heading", { name: "Billing & Payments" })).toBeVisible();
  await receptionContext.close();

  // --- Nurse: independent login lands on triage, completes triage.
  const nurseContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const nursePage = await nurseContext.newPage();
  await login(nursePage, "nurse@clinicopus.local");
  await expect(nursePage).toHaveURL(/\/triage$/);
  await expect(nursePage.getByRole("heading", { name: "Triage", exact: true })).toBeVisible();
  await expect(nursePage.getByRole("link", { name: "Billing & Payments" })).toHaveCount(0);

  const triageRow = nursePage.getByRole("listitem").filter({ hasText: patientName });
  await expect(triageRow).toBeVisible();
  await triageRow.click();
  await steadyFill(nursePage, "Chief complaint", "Handoff cough");
  await nursePage.getByRole("button", { name: "Complete triage" }).click();
  await expect(nursePage.getByText("Triage recorded for " + patientName)).toBeVisible();
  await nurseContext.close();

  // --- Doctor: independent login lands on consultations, signs the note.
  const doctorContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const doctorPage = await doctorContext.newPage();
  await login(doctorPage, "doctor@clinicopus.local");
  await expect(doctorPage).toHaveURL(/\/consultations$/);
  await expect(doctorPage.getByRole("link", { name: "Billing & Payments" })).toHaveCount(0);

  const consultRow = doctorPage.getByRole("listitem").filter({ hasText: patientName });
  await expect(consultRow).toBeVisible();
  await consultRow.click();
  await doctorPage.getByRole("button", { name: "Start encounter" }).click();
  await expect(doctorPage.getByText(/ENC-/)).toBeVisible();
  await doctorPage.getByLabel("Consultation note").fill("Assessment: mild. Plan: review.");
  await doctorPage.getByRole("button", { name: "Sign consultation" }).click();
  await doctorPage.getByRole("button", { name: "Confirm signature" }).click();
  await expect(doctorPage.getByText("This consultation is signed and immutable.")).toBeVisible();
  await expect(doctorPage.getByRole("button", { name: "Create invoice" })).toHaveCount(0);
  await doctorContext.close();

  // --- Cashier: fresh session, finds the reception-created unpaid invoice and collects it.
  const cashierContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const cashierPage = await cashierContext.newPage();
  await login(cashierPage, "cashier@clinicopus.local");
  await expect(cashierPage).toHaveURL(/\/billing$/);
  await expect(cashierPage.getByRole("heading", { name: "Billing & Payments" })).toBeVisible();

  await steadyFill(cashierPage, "Search invoices", patientName);
  const invoiceRow = cashierPage.getByRole("listitem").filter({ hasText: patientName });
  await expect(invoiceRow).toBeVisible();
  await invoiceRow.getByRole("button", { name: "Collect" }).click();
  await cashierPage.getByRole("button", { name: "Post payment" }).click();
  await expect(cashierPage.getByText("Payment recorded. Receipt RCT-")).toBeVisible();
  await cashierPage.screenshot({ path: path.join(REVIEW_DIR, "handoff-cashier-receipt.png"), fullPage: true });
  await cashierContext.close();
});

test("authentication guards and role landing pages", async ({ browser }) => {
  // Wrong password is rejected with a friendly message.
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await context.newPage();
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", "wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /invalid credentials/i })).toBeVisible();

  // A logged-out user cannot open an authenticated route directly.
  await page.goto("/billing");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await context.close();
});

test("responsive rendering at supported widths", async ({ browser }) => {
  fs.mkdirSync(REVIEW_DIR, { recursive: true });
  for (const [width, height] of [[1366, 768], [1024, 768], [768, 1024]] as const) {
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage();
    await login(page, "demo", DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/overview$/);
    await page.getByRole("heading", { name: "Today's Queue" }).waitFor();
    const shotName = "responsive-" + width + "x" + height + ".png";
    await page.screenshot({ path: path.join(REVIEW_DIR, shotName), fullPage: true });
    await context.close();
  }
});
