import { expect, test } from "@playwright/test";

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
