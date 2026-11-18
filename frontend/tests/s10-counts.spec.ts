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

test("S-10 blind count submits, approves and posts the exact correction", async ({ page }) => {
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
      code: `S10-${suffix}`,
      generic_name: `Synthetic S10 ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      strength: "250 mg",
      category: "MEDICINE",
    },
  });
  expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
  const product = (await productResponse.json()) as { id: string; generic_name: string };
  await page.request.post(`${API}/api/v1/inventory/prices/`, {
    headers: { ...headers, "Idempotency-Key": `s10-price-${suffix}` },
    data: {
      product_id: product.id,
      amount: "500.00",
      effective_from: new Date().toISOString().slice(0, 10),
    },
  });
  const locations = (await (
    await page.request.get(`${API}/api/v1/inventory/locations/`, { headers })
  ).json()) as Array<{ id: string; is_default: boolean }>;
  const locationId = locations.find((item) => item.is_default)?.id ?? locations[0].id;
  const receipt = await page.request.post(`${API}/api/v1/inventory/receipts/`, {
    headers: { ...headers, "Idempotency-Key": `s10-receipt-${suffix}` },
    data: {
      receipt_no: `GRN-S10-${suffix}`,
      lines: [
        {
          product_id: product.id,
          location_id: locationId,
          batch_no: `B-S10-${suffix}`,
          expiry_date: new Date(Date.now() + 365 * 24 * 3600 * 1000)
            .toISOString()
            .slice(0, 10),
          quantity: "100.00",
        },
      ],
    },
  });
  expect(receipt.ok(), await receipt.text()).toBeTruthy();

  await page.goto("/inventory");
  await expect(page.getByText("Blind stock count", { exact: true })).toBeVisible();
  const sheetLoaded = page.waitForResponse(
    (response) =>
      /\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/$/.test(response.url()) &&
      response.request().method() === "GET"
  );
  await page.getByRole("button", { name: "Open count", exact: true }).click();
  expect((await sheetLoaded).status()).toBe(200);
  await expect(page.getByText(/blind sheet \(expected quantities hidden\)/)).toBeVisible();
  const counted = page.getByLabel(/Counted quantity/).first();
  await counted.fill("95.00");
  const submitted = page.waitForResponse(
    (response) =>
      /\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/submit\/$/.test(response.url()) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Submit count", exact: true }).click();
  expect((await submitted).status()).toBe(200);
  await expect(page.getByText(/Count submitted/)).toBeVisible();

  const approved = page.waitForResponse(
    (response) =>
      /\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/approve\/$/.test(response.url()) &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Approve count", exact: true }).click();
  expect((await approved).status()).toBe(200);
  await expect(page.getByText(/Stock count approved/)).toBeVisible();
  await expect(page.getByText(/variance -5\.00/)).toBeVisible();
  await expect(page.getByText(/95\.00/).first()).toBeVisible();
});
