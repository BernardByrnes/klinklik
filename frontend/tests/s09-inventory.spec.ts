import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

async function steadyFill(page: Page, label: string, value: string) {
  const locator = page.getByLabel(label, { exact: true });
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await locator.fill(value);
    if ((await locator.inputValue()) === value) {
      await page.waitForTimeout(150);
      if ((await locator.inputValue()) === value) return;
    }
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
  await expect(page).toHaveURL(/\/overview$/);
}

test("S-09 receives non-expired stock, warns near expiry and refuses expired batches", async ({
  page,
}) => {
  await login(page);
  const sessionResponse = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  const headers = {
    Authorization: `Bearer ${session.access_token}`,
    "X-Facility-Id": session.facilities[0].id,
    "Content-Type": "application/json",
  };
  const suffix = Date.now().toString().slice(-6) + Math.trunc(Math.random() * 1000);
  const productResponse = await page.request.post(`${API}/api/v1/inventory/products/`, {
    headers,
    data: {
      code: `S09-${suffix}`,
      generic_name: `Synthetic S09 ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      strength: "500 mg",
      category: "MEDICINE",
    },
  });
  expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
  const product = (await productResponse.json()) as { id: string; generic_name: string };
  const locationsResponse = await page.request.get(`${API}/api/v1/inventory/locations/`, {
    headers,
  });
  expect(locationsResponse.ok()).toBeTruthy();
  const locations = (await locationsResponse.json()) as Array<{ id: string; is_default: boolean }>;
  expect(locations.length).toBeGreaterThan(0);

  await page.goto("/inventory");
  await expect(page.getByRole("heading", { name: "Inventory" })).toBeVisible();
  await expect(page.getByText("Receive stock", { exact: true })).toBeVisible();
  await page.getByLabel("Product", { exact: true }).selectOption(product.id);
  await steadyFill(page, "Batch number", `B-${suffix}`);
  const soon = new Date();
  soon.setDate(soon.getDate() + 30);
  await steadyFill(page, "Expiry date", soon.toISOString().slice(0, 10));
  await steadyFill(page, "Quantity", "25.00");
  const receiptPosted = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/receipts/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Post receipt", exact: true }).click();
  expect((await receiptPosted).status()).toBe(201);
  await expect(page.getByText(/Stock received on GRN-/)).toBeVisible();
  await expect(page.getByText(/90-day warning horizon/)).toBeVisible();
  await expect(page.getByText(product.generic_name).first()).toBeVisible();
  await expect(page.getByText("IN_GRN").first()).toBeVisible();

  // A past expiry is refused with no stock movement.
  await steadyFill(page, "Batch number", `EXP-${suffix}`);
  await steadyFill(page, "Expiry date", "2020-01-01");
  await steadyFill(page, "Quantity", "5.00");
  const refused = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/receipts/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Post receipt", exact: true }).click();
  expect((await refused).status()).toBe(422);
  await expect(page.getByText(/expired stock cannot be received/i)).toBeVisible();
});
