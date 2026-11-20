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

test("S-29-R3 uncertain receipt retry reuses one immutable intent", async ({ page }) => {
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
      code: `S29R3-${suffix}`,
      generic_name: `Synthetic S29 R3 ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      strength: "500 mg",
      category: "MEDICINE",
    },
  });
  expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
  const product = (await productResponse.json()) as { id: string };

  await page.goto("/inventory");
  await page.getByLabel("Product", { exact: true }).selectOption(product.id);
  await steadyFill(page, "Batch number", `R3-${suffix}`);
  const expiry = new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString().slice(0, 10);
  await steadyFill(page, "Expiry date", expiry);
  await steadyFill(page, "Quantity", "25.00");

  const attempts: Array<{ key: string | undefined; body: string | null }> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/receipts/")
    ) {
      attempts.push({
        key: request.headers()["idempotency-key"],
        body: request.postData(),
      });
    }
  });
  let lostResponse = false;
  await page.route("**/api/v1/inventory/receipts/", async (route) => {
    if (!lostResponse) {
      lostResponse = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "Post receipt", exact: true }).click();
  await expect(page.getByText(/receipt outcome is uncertain/i)).toBeVisible();
  await page.getByRole("button", { name: "Retry uncertain receipt", exact: true }).click();
  await expect(page.getByText(/Stock received on GRN-/)).toBeVisible();

  expect(attempts).toHaveLength(2);
  expect(attempts[1].key).toBe(attempts[0].key);
  expect(attempts[1].key).toBeTruthy();
  expect(attempts[1].body).toBe(attempts[0].body);
  const body = JSON.parse(attempts[0].body ?? "{}") as { receipt_no: string };
  expect(body.receipt_no).toMatch(/^GRN-/);

  const verifySession = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(verifySession.ok(), await verifySession.text()).toBeTruthy();
  const verifyBody = (await verifySession.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  const verifyHeaders = {
    Authorization: `Bearer ${verifyBody.access_token}`,
    "X-Facility-Id": verifyBody.facilities[0].id,
  };
  const stock = await page.request.get(`${API}/api/v1/inventory/stock/`, {
    headers: verifyHeaders,
  });
  expect(stock.ok(), await stock.text()).toBeTruthy();
  const stockBody = (await stock.json()) as Array<{
    product_id: string;
    usable_quantity: string;
  }>;
  const row = stockBody.find((item) => item.product_id === product.id);
  expect(row?.usable_quantity).toBe("25.00");
  const movements = await page.request.get(`${API}/api/v1/inventory/movements/`, {
    headers: verifyHeaders,
  });
  expect(movements.ok(), await movements.text()).toBeTruthy();
  const movementBody = (await movements.json()) as Array<{
    product: string;
    movement_type: string;
    quantity: string;
    source_type: string;
    source_id: string;
  }>;
  const receiptMovements = movementBody.filter(
    (item) => item.product === product.id && item.movement_type === "IN_GRN"
  );
  expect(receiptMovements).toHaveLength(1);
  expect(receiptMovements[0].quantity).toBe("25.00");
  expect(receiptMovements[0].source_type).toBe("StockReceiptLine");
  expect(receiptMovements[0].source_id).toBeTruthy();
});
