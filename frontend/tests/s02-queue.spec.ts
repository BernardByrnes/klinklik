import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt++) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(250);
  }
  throw new Error(`Input "${label}" did not hold its value`);
}

async function login(page: Page) {
  await page.goto("/");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  const organisationId = process.env.CLINICOPUS_E2E_ORGANISATION_ID;
  if (organisationId) await steadyFill(page, "Organisation ID", organisationId);
  await steadyFill(page, "Username", "demo");
  await steadyFill(page, "Password", DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

async function expectNamedControls(page: Page) {
  const unnamedControls = await page.locator("button, input, select, textarea, a").evaluateAll((controls) =>
    controls
      .filter((control) => {
        const element = control as HTMLElement;
        const labelledBy = element.getAttribute("aria-labelledby");
        const labelled = element.getAttribute("aria-label") || element.getAttribute("title");
        const associatedLabel = element.id
          ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)?.textContent
          : null;
        return !labelledBy && !labelled && !associatedLabel?.trim() && !element.textContent?.trim();
      })
      .map((control) => control.outerHTML),
  );
  expect(unnamedControls).toEqual([]);
}

test("S-02 queue exposes canonical status filters and a keyboard focus path", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/queue");

  await expect(page.getByRole("heading", { name: "Queue", exact: true })).toBeVisible();
  await expect(page.getByRole("tablist", { name: "Queue status filter", exact: true })).toBeVisible();
  for (const name of ["All", "Awaiting triage", "In service", "Completed stage", "In service (consultation)"]) {
    await expect(page.getByRole("tab", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByLabel("Filter queue", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Queue entries/ })).toBeVisible();
  await expectNamedControls(page);

  const triageTab = page.getByRole("tab", { name: "Awaiting triage", exact: true });
  await triageTab.focus();
  await expect(triageTab).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tab", { name: "In service", exact: true })).toBeFocused();
});

test("S-02 triage renders its accessible empty and selection states", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/triage");

  await expect(page.getByRole("heading", { name: "Triage", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Awaiting triage/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Triage record", exact: true })).toBeVisible();
  await expect(page.getByText("No patient selected.", { exact: true })).toBeVisible();
  await expectNamedControls(page);
});
