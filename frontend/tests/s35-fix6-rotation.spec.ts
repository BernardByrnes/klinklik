import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";
const SECOND_FACILITY_NAME = "S35 Rotation Facility";

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
    code="S35_ROTATION",
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

async function switchFacility(page: Page, name: string) {
  await page.getByRole("button", { name: "Switch facility" }).click();
  await page.getByRole("listbox", { name: "Facilities" }).getByRole("option", { name }).click();
  await expect(page.getByRole("button", { name: "Switch facility" })).toContainText(name);
}

test("S-35 Fix 6 same-authority refresh preserves a non-default facility and sync marker", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const second = ensureSecondFacility();
  await login(page);
  await page.goto("/patients");
  await switchFacility(page, second.name);
  const status = page.getByTestId("connectivity-status");
  await expect(status).toContainText("Patients last synced");
  const before = await status.textContent();
  const root = page.locator("[data-authority-epoch]");
  const epochBefore = await root.getAttribute("data-authority-epoch");

  await page.clock.install();
  const refreshed = page.waitForResponse(
    (response) => response.url().endsWith("/auth/refresh/") && response.request().method() === "POST",
  );
  let forced = false;
  await page.route("**/api/v1/clinic/queue/", async (route) => {
    if (!forced) {
      forced = true;
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Access token is revoked or expired." }),
      });
      return;
    }
    await route.continue();
  });
  await page.clock.fastForward(30_000);
  expect((await refreshed).status()).toBe(200);

  await expect(page.getByRole("button", { name: "Switch facility" })).toContainText(second.name);
  await expect(status).toContainText("Patients last synced");
  expect(await status.textContent()).toBe(before);
  expect(await root.getAttribute("data-authority-epoch")).toBe(epochBefore);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
});

test("S-35 Fix 6 refresh followed by refusal requires a safe restart", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);
  await page.goto("/patients");
  await expect(page.getByTestId("connectivity-status")).toContainText("Patients last synced");
  await page.clock.install();

  let startedRefresh: (() => void) | null = null;
  const refreshStarted = new Promise<void>((resolve) => {
    startedRefresh = resolve;
  });
  await page.route("**/api/v1/auth/refresh/", async (route) => {
    startedRefresh?.();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  let forced = false;
  await page.route("**/api/v1/clinic/queue/", async (route) => {
    if (!forced) {
      forced = true;
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Access token is revoked or expired." }),
      });
      return;
    }
    await route.continue();
  });

  await page.clock.fastForward(30_000);
  await refreshStarted;
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);

  await page.goto("/patients");
  await expect(page).toHaveURL(/\/login$/);
});

test("S-35 Fix 6 facility switch during a pending fetch drops the old response", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const second = ensureSecondFacility();
  await login(page);
  await page.goto("/patients");
  const status = page.getByTestId("connectivity-status");
  await expect(status).toContainText("Patients last synced");
  await page.clock.install();

  let startedFetch: (() => void) | null = null;
  const fetchStarted = new Promise<void>((resolve) => {
    startedFetch = resolve;
  });
  await page.route("**/api/v1/clinic/queue/", async (route) => {
    startedFetch?.();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });

  await page.clock.fastForward(30_000);
  await fetchStarted;
  await switchFacility(page, second.name);
  await expect(status).toContainText("not yet synced");
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
});
