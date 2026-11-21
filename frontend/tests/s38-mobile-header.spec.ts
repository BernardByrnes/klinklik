import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";
const SECOND_FACILITY_NAME = "S38 Mobile Branch";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) return;
    await page.waitForTimeout(150);
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
  await expect(page).toHaveURL(/\/(overview|patients)$/);
}

function ensureSecondFacility() {
  const script = `
from tenancy.models import Organisation, Facility
org = Organisation.objects.get(slug="clinicopus-demo")
facility, _ = Facility.objects.update_or_create(
    organisation=org,
    code="S38_MOBILE",
    defaults={"name": "${SECOND_FACILITY_NAME}", "mode": "CLINIC", "timezone": "Africa/Kampala", "is_active": True},
)
print(facility.id)
`;
  const output = execFileSync("python", ["../backend/manage.py", "shell", "-c", script], {
    cwd: path.resolve(__dirname, ".."),
    encoding: "utf8",
  });
  const id = output.trim().split(/\r?\n/).pop();
  if (!id) throw new Error("could not seed second facility");
  return { id, name: SECOND_FACILITY_NAME };
}

async function openSidebar(page: Page) {
  const navList = page.getByRole("navigation", { name: "Main navigation" });
  if (await navList.isVisible()) return;
  const nav = page.getByRole("button", { name: "Open navigation" });
  await expect(nav).toBeVisible();
  await nav.tap();
  await expect(navList).toBeVisible();
}

test("S-38 390px shell keeps status readable and recovery reachable", async ({ page }) => {
  test.setTimeout(120_000);
  const second = ensureSecondFacility();
  await login(page);
  await page.goto("/patients");
  await expect(page).toHaveURL(/\/patients$/);

  let lost = false;
  await page.route("**/api/v1/reception/patients/register/", async (route) => {
    if (!lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await steadyFill(page, "First name", "S38");
  await steadyFill(page, "Last name", "Mobile");
  await steadyFill(page, "Phone", "0751234567");
  await page
    .getByLabel("Register patient")
    .getByRole("button", { name: "Register patient", exact: true })
    .click();
  const review = page.getByTestId("pending-intent-review");
  await expect(review).toBeVisible({ timeout: 15_000 });

  const metrics = await page.evaluate(() => {
    const status = document.querySelector('[data-testid="connectivity-status"]');
    const rect = status?.getBoundingClientRect();
    return {
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      statusRight: Math.round(rect?.right ?? 0),
      statusText: (status as HTMLElement | null)?.innerText ?? "",
      statusTitle: (status as HTMLElement | null)?.title ?? "",
      statusAria: (status as HTMLElement | null)?.getAttribute("aria-label") ?? "",
    };
  });
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewportWidth);
  expect(metrics.statusRight).toBeLessThanOrEqual(metrics.viewportWidth);
  expect(metrics.statusText).toContain("Online");
  expect(metrics.statusTitle).toContain("last synced");
  expect(metrics.statusAria).toContain("last synced");

  await review.tap();
  const retry = page.getByRole("button", { name: "Retry", exact: true });
  await expect(retry).toBeVisible();
  await retry.tap();
  await expect(page.getByText(/registered as P-/)).toBeVisible({ timeout: 15_000 });
  await expect(review).toHaveCount(0);

  // Account menu by keyboard and by tap.
  const account = page.getByRole("button", { name: "Account menu" });
  await account.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu")).toBeVisible();
  await page.locator("main").click({ position: { x: 5, y: 5 } });
  await account.tap();
  await expect(page.getByRole("menu")).toBeVisible();
  await page.locator("main").click({ position: { x: 5, y: 5 } });

  // Facility switcher by keyboard and by tap.
  await openSidebar(page);
  const switcher = page.getByRole("button", { name: "Switch facility" });
  await switcher.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("listbox", { name: "Facilities" })).toBeVisible();
  const option = page.getByRole("option", { name: second.name });
  await option.focus();
  await page.keyboard.press("Enter");
  await expect(switcher).toContainText(second.name);

  await openSidebar(page);
  await switcher.tap();
  await expect(page.getByRole("listbox", { name: "Facilities" })).toBeVisible();
  await page.getByRole("option", { name: "Main Branch" }).tap();
  await expect(switcher).toContainText("Main Branch");
});

const ROUTES = [
  ["patients", "/patients"],
  ["lab", "/lab"],
  ["consultations", "/consultations"],
  ["pharmacy", "/pharmacy"],
  ["inventory", "/inventory"],
  ["billing", "/billing"],
];

for (const [width, label] of [[390, "mobile"], [1366, "desktop"]] as const) {
  test(`S-38 ${label} smoke across six workspaces`, async ({ page }) => {
    test.setTimeout(180_000);
    await login(page);
    await page.setViewportSize({ width, height: label === "mobile" ? 844 : 900 });
    for (const [name, route] of ROUTES) {
      await page.goto(route);
      await expect(page).toHaveURL(new RegExp(`${route.replace("/", "\\/")}$`));
      await expect(page.getByTestId("connectivity-status")).toBeVisible();
      const metrics = await page.evaluate(() => {
        const status = document.querySelector('[data-testid="connectivity-status"]');
        const rect = status?.getBoundingClientRect();
        return {
          pathname: location.pathname,
          scrollWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          statusRight: Math.round(rect?.right ?? 0),
        };
      });
      expect(metrics.pathname).toBe(route);
      expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewportWidth);
      expect(metrics.statusRight).toBeLessThanOrEqual(metrics.viewportWidth);
    }
  });
}
