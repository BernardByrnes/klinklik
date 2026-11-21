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
  await page.getByRole("button", { name: "Add receipt line", exact: true }).click();
  await steadyFill(page, "Batch number 2", `B2-${suffix}`);
  await steadyFill(page, "Expiry date 2", soon.toISOString().slice(0, 10));
  await steadyFill(page, "Quantity 2", "15.00");
  let receiptBody = "";
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/receipts/")
    ) {
      receiptBody = request.postData() ?? "";
    }
  });
  const receiptPosted = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/receipts/") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Post receipt", exact: true }).click();
  expect((await receiptPosted).status()).toBe(201);
  const postedReceipt = JSON.parse(receiptBody) as {
    receipt_no: string;
    lines: Array<{ batch_no: string; quantity: string }>;
  };
  expect(postedReceipt.lines).toHaveLength(2);
  expect(postedReceipt.receipt_no).toMatch(/^GRN-/);
  expect(postedReceipt.lines.map((line) => line.quantity)).toEqual(["25.00", "15.00"]);
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

const CATALOGUE_HEADER =
  "category,code,dispensing_unit,dosage_form,generic_name,active,brand_name,controlled,currency,effective_from,pack_description,pack_price,prescription_only,price,strength";

function catalogueRow(code: string, packPrice = "") {
  return `MEDICINE,${code},TABLET,TABLET,Synthetic Web ${code},true,,false,UGX,2026-01-01,,${packPrice},,100.00,500 mg`;
}

async function refreshSession(page: Page) {
  const response = await page.request.post(`${API}/api/v1/auth/refresh/`);
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as {
    access_token: string;
    facilities: Array<{ id: string }>;
  };
  return {
    Authorization: `Bearer ${body.access_token}`,
    "X-Facility-Id": body.facilities[0].id,
    "Content-Type": "application/json",
  };
}

test("S-41 catalogue preview reviews errors and imports only valid rows", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const goodCode = `S41WEB${suffix}`;
  const badCode = `S41BAD${suffix}`;
  const content =
    CATALOGUE_HEADER + "\n" + catalogueRow(goodCode) + "\n" + catalogueRow(badCode, "bad") + "\n";

  await page.goto("/inventory");
  await expect(page.getByRole("heading", { name: "Catalogue CSV review" })).toBeVisible();
  const fileInput = page.getByLabel("Catalogue CSV file", { exact: true });
  await fileInput.focus();
  expect(await fileInput.evaluate((element) => element === document.activeElement)).toBe(true);
  await fileInput.setInputFiles({
    name: "s41-review.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(content, "utf-8"),
  });

  const previewPosted = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/catalogue/import/preview/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  expect((await previewPosted).status()).toBe(200);
  const preview = page.locator("[data-catalogue-preview]");
  await expect(preview).toContainText("s41-review.csv");
  await expect(preview).toContainText("Accepted 1 · skipped 0 · errors 1");
  await expect(preview).toContainText("Line 3: pack_price is invalid");
  await expect(page.getByRole("button", { name: "Import catalogue", exact: true })).toBeDisabled();

  // Changing the file invalidates the review rather than importing stale content.
  await fileInput.setInputFiles({
    name: "s41-review.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(content, "utf-8"),
  });
  await expect(preview).toHaveCount(0);

  await page.getByLabel("Valid rows only", { exact: true }).check();
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  await expect(preview).toContainText("Accepted 1 · skipped 0 · errors 1");
  await page.getByRole("button", { name: "Review valid rows only", exact: true }).click();
  await expect(page.getByText(/eligible row\(s\) will be imported/)).toBeVisible();

  const attempts: Array<{ key: string | undefined; body: string | null }> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/catalogue/import/")
    ) {
      attempts.push({
        key: request.headers()["idempotency-key"],
        body: request.postData(),
      });
    }
  });
  const imported = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/catalogue/import/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm valid rows import", exact: true }).click();
  expect((await imported).status()).toBe(201);
  await expect(page.locator("[data-catalogue-result]")).toContainText("applied 1");
  expect(attempts).toHaveLength(1);
  const sent = JSON.parse(attempts[0].body ?? "{}") as {
    file_hash: string;
    content: string;
    mode: string;
  };
  expect(sent.file_hash).toMatch(/^[0-9a-f]{64}$/);
  expect(sent.content).toBe(content);
  expect(sent.mode).toBe("VALID_ROWS_ONLY");
  expect(await fileInput.inputValue()).toBe("");

  const headers = await refreshSession(page);
  const products = await page.request.get(`${API}/api/v1/inventory/products/`, { headers });
  expect(products.ok(), await products.text()).toBeTruthy();
  const productRows = (await products.json()) as Array<{ code: string }>;
  expect(productRows.some((row) => row.code === goodCode)).toBe(true);
  expect(productRows.some((row) => row.code === badCode)).toBe(false);
});

test("S-41 uncertain catalogue import retries the exact key at 390px", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/inventory");
  const suffix = Date.now().toString().slice(-6);
  const code = `S41RETRY${suffix}`;
  const content = CATALOGUE_HEADER + "\n" + catalogueRow(code) + "\n";
  await page.getByLabel("Catalogue CSV file", { exact: true }).setInputFiles({
    name: "s41-retry.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(content, "utf-8"),
  });
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  await expect(page.locator("[data-catalogue-preview]")).toContainText("Accepted 1");

  const attempts: Array<{ key: string | undefined; body: string | null }> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/catalogue/import/")
    ) {
      attempts.push({
        key: request.headers()["idempotency-key"],
        body: request.postData(),
      });
    }
  });
  let lostResponse = false;
  await page.route("**/api/v1/inventory/catalogue/import/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    if (!lostResponse) {
      lostResponse = true;
      const committed = await route.fetch();
      expect(committed.status()).toBe(201);
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "Import catalogue", exact: true }).click();
  await expect(page.locator("[data-catalogue-reconcile]")).toContainText(
    "import response is uncertain",
  );
  expect(attempts).toHaveLength(1);

  const retried = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/catalogue/import/") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Retry exact import", exact: true }).click();
  expect((await retried).status()).toBe(201);
  expect(attempts).toHaveLength(2);
  expect(attempts[1].key).toBe(attempts[0].key);
  expect(attempts[1].body).toBe(attempts[0].body);
  await expect(page.locator("[data-catalogue-result]")).toContainText("applied 1");
});

test("S-41 a duplicate conflict is reconciled from a fresh preview", async ({ page }) => {
  await login(page);
  const suffix = Date.now().toString().slice(-6);
  const duplicateCode = `S41DUP${suffix}`;
  const newCode = `S41NEW${suffix}`;
  await page.goto("/inventory");
  const content = CATALOGUE_HEADER + "\n" + catalogueRow(duplicateCode) + "\n" + catalogueRow(newCode) + "\n";
  await page.getByLabel("Catalogue CSV file", { exact: true }).setInputFiles({
    name: "s41-conflict.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(content, "utf-8"),
  });
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  const preview = page.locator("[data-catalogue-preview]");
  await expect(preview).toContainText("Accepted 2 · skipped 0 · errors 0");

  // A competing writer creates the duplicate after the review, so the server
  // conflict is real even though the preview was clean.
  const headers = await refreshSession(page);
  const existing = await page.request.post(`${API}/api/v1/inventory/products/`, {
    headers,
    data: {
      code: duplicateCode,
      generic_name: `Synthetic Existing ${suffix}`,
      dosage_form: "TABLET",
      dispensing_unit: "TABLET",
      category: "MEDICINE",
    },
  });
  expect(existing.ok(), await existing.text()).toBeTruthy();

  const conflict = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/inventory/catalogue/import/") &&
      response.request().method() === "POST" &&
      response.status() === 409,
  );
  await page.getByRole("button", { name: "Import catalogue", exact: true }).click();
  expect((await conflict).status()).toBe(409);
  await expect(page.locator("[data-catalogue-reconcile]")).toContainText("reviewed file was refused");

  await page.getByRole("button", { name: "Refresh preview", exact: true }).click();
  await expect(preview).toContainText("Accepted 2 · skipped 1 · errors 0");
  await page.getByLabel("Valid rows only", { exact: true }).check();
  await page.getByRole("button", { name: "Preview CSV", exact: true }).click();
  await expect(preview).toContainText("skipped 1");
  await page.getByRole("button", { name: "Review valid rows only", exact: true }).click();
  await page.getByRole("button", { name: "Confirm valid rows import", exact: true }).click();
  await expect(page.locator("[data-catalogue-result]")).toContainText("skipped 1");

  const verified = await refreshSession(page);
  const products = await page.request.get(`${API}/api/v1/inventory/products/`, {
    headers: verified,
  });
  expect(products.ok(), await products.text()).toBeTruthy();
  const rows = (await products.json()) as Array<{ code: string; generic_name: string }>;
  expect(rows.filter((row) => row.code === duplicateCode)).toHaveLength(1);
  expect(rows.find((row) => row.code === duplicateCode)?.generic_name).toBe(
    `Synthetic Existing ${suffix}`,
  );
  expect(rows.some((row) => row.code === newCode)).toBe(true);
});
