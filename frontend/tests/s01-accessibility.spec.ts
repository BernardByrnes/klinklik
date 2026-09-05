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
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("login controls have accessible names and a visible keyboard focus path", async ({ page }) => {
  await page.goto("/login");
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });

  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByLabel("Organisation ID", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();

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

  await page.getByLabel("Username", { exact: true }).focus();
  await expect(page.getByLabel("Username", { exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Organisation ID", { exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeFocused();
});

test("S-01 registration and check-in workflow controls are accessible", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/patients");
  await expect(page.getByRole("heading", { name: "Patients", exact: true })).toBeVisible();

  const registrationForm = page.locator('form[aria-label="Register patient"]');
  await expect(registrationForm).toBeVisible();
  const unnamedControls = await registrationForm.locator("button, input, select, textarea, a").evaluateAll((controls) =>
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

  const suffix = Date.now().toString().slice(-7);
  await steadyFill(page, "First name", "A11y");
  await steadyFill(page, "Last name", `Reception${suffix}`);
  await steadyFill(page, "Phone", `0708${suffix}`);
  await registrationForm.getByRole("button", { name: "Register patient", exact: true }).click();
  await expect(page.getByText(new RegExp("registered as P-"))).toBeVisible();

  const visitTypes = page.getByRole("radiogroup", { name: "Visit type", exact: true });
  const payerTypes = page.getByRole("radiogroup", { name: "Payer", exact: true });
  const checkInButton = page.getByRole("button", { name: "Check in patient", exact: true });
  await expect(visitTypes).toBeVisible();
  await expect(payerTypes).toBeVisible();
  await expect(visitTypes.getByRole("radio", { name: "Outpatient — new", exact: true })).toBeChecked();
  await expect(checkInButton).toBeEnabled();

  await page.getByLabel("First name", { exact: true }).focus();
  await expect(page.getByLabel("First name", { exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Last name", { exact: true })).toBeFocused();
  await checkInButton.focus();
  await expect(checkInButton).toBeFocused();
});
