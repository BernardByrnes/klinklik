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
  await page.request.get(`${API}/api/v1/inventory/locations/`, { headers });
  const locationResponse = await page.request.post(`${API}/api/v1/inventory/locations/`, {
    headers,
    data: { code: `S10-LOC-${suffix}`, name: `S10 Store ${suffix}`, location_type: "STORE" },
  });
  expect(locationResponse.ok(), await locationResponse.text()).toBeTruthy();
  const location = (await locationResponse.json()) as { id: string };
  const locationId = location.id;
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
  await page.getByLabel("Location", { exact: true }).selectOption(locationId);
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

test("S-29-R2 blank count lines are identified and explicit zero is submitted exactly", async ({
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
  const locationResponse = await page.request.post(`${API}/api/v1/inventory/locations/`, {
    headers,
    data: { code: `S29R2-LOC-${suffix}`, name: `S29R2 Store ${suffix}`, location_type: "STORE" },
  });
  expect(locationResponse.ok(), await locationResponse.text()).toBeTruthy();
  const locationId = ((await locationResponse.json()) as { id: string }).id;
  const expiry = new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString().slice(0, 10);
  const batches = [`B-R2A-${suffix}`, `B-R2B-${suffix}`];

  for (const [index, batch] of batches.entries()) {
    const productResponse = await page.request.post(`${API}/api/v1/inventory/products/`, {
      headers,
      data: {
        code: `S29R2-${index}-${suffix}`,
        generic_name: `Synthetic S29 R2 product ${index} ${suffix}`,
        dosage_form: "TABLET",
        dispensing_unit: "TABLET",
        strength: index === 0 ? "250 mg" : "125 mg",
        category: "MEDICINE",
      },
    });
    expect(productResponse.ok(), await productResponse.text()).toBeTruthy();
    const product = (await productResponse.json()) as { id: string };
    await page.request.post(`${API}/api/v1/inventory/prices/`, {
      headers: { ...headers, "Idempotency-Key": `s29-r2-price-${index}-${suffix}` },
      data: {
        product_id: product.id,
        amount: "500.00",
        effective_from: new Date().toISOString().slice(0, 10),
      },
    });
    const receipt = await page.request.post(`${API}/api/v1/inventory/receipts/`, {
      headers: { ...headers, "Idempotency-Key": `s29-r2-receipt-${index}-${suffix}` },
      data: {
        receipt_no: `GRN-S29R2-${index}-${suffix}`,
        lines: [
          {
            product_id: product.id,
            location_id: locationId,
            batch_no: batch,
            expiry_date: expiry,
            quantity: index === 0 ? "100.00" : "50.00",
          },
        ],
      },
    });
    expect(receipt.ok(), await receipt.text()).toBeTruthy();
  }

  await page.goto("/inventory");
  await expect(page.getByText("Blind stock count", { exact: true })).toBeVisible();
  await page.getByLabel("Location", { exact: true }).selectOption(locationId);
  await page.getByRole("button", { name: "Open count", exact: true }).click();
  await expect(page.getByLabel(`Counted quantity ${batches[0]}`)).toBeVisible();
  await expect(page.getByLabel(`Counted quantity ${batches[1]}`)).toBeVisible();

  let submitRequests = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/submit\/$/.test(request.url())
    ) {
      submitRequests += 1;
    }
  });
  await page.getByRole("button", { name: "Submit count", exact: true }).click();
  await page.waitForTimeout(500);
  expect(submitRequests).toBe(0);
  await expect(page.getByText(/Enter a counted quantity for every line/)).toBeVisible();
  await expect(page.getByLabel(`Counted quantity ${batches[0]}`)).toHaveAttribute(
    "aria-invalid",
    "true"
  );

  await page.getByLabel(`Counted quantity ${batches[0]}`).fill("95.00");
  await page.getByLabel(`Counted quantity ${batches[1]}`).fill("0");
  const submitRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      /\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/submit\/$/.test(request.url())
  );
  await page.getByRole("button", { name: "Submit count", exact: true }).click();
  const body = JSON.parse((await submitRequest).postData() ?? "{}") as {
    lines: Array<{ counted_qty: string }>;
  };
  const submittedValues = body.lines.map((line) => line.counted_qty);
  expect(submittedValues).toEqual(expect.arrayContaining(["95.00", "0"]));
  expect(submittedValues).not.toContain("0.00");
  await expect(page.getByText(/Count submitted/)).toBeVisible();
});

async function signInAs(page: Page, username: string, password: string) {
  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForSelector('html[data-app-ready="1"]', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login$/);
  await steadyFill(page, "Username", username);
  await steadyFill(page, "Password", password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/(overview|inventory)$/);
}

test("S-32 independent approver discovers a submitted count from their own session", async ({
  page,
}) => {
  await login(page);
  const sessionResponse = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
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
  const product = (await (
    await page.request.post(`${API}/api/v1/inventory/products/`, {
      headers,
      data: {
        code: `S32AP-${suffix}`,
        generic_name: `S32 approver product ${suffix}`,
        dosage_form: "TABLET",
        dispensing_unit: "TABLET",
        strength: "250 mg",
        category: "MEDICINE",
      },
    })
  ).json()) as { id: string };
  const location = (await (
    await page.request.post(`${API}/api/v1/inventory/locations/`, {
      headers,
      data: { code: `S32APLOC-${suffix}`, name: `S32 approver store ${suffix}`, location_type: "STORE" },
    })
  ).json()) as { id: string };
  await page.request.post(`${API}/api/v1/inventory/prices/`, {
    headers: { ...headers, "Idempotency-Key": `s32ap-price-${suffix}` },
    data: {
      product_id: product.id,
      amount: "500.00",
      effective_from: new Date().toISOString().slice(0, 10),
    },
  });
  await page.request.post(`${API}/api/v1/inventory/receipts/`, {
    headers: { ...headers, "Idempotency-Key": `s32ap-receipt-${suffix}` },
    data: {
      receipt_no: `GRN-S32AP-${suffix}`,
      lines: [
        {
          product_id: product.id,
          location_id: location.id,
          batch_no: `B-S32AP-${suffix}`,
          expiry_date: new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10),
          quantity: "100.00",
        },
      ],
    },
  });
  const opened = await page.request.post(`${API}/api/v1/inventory/counts/open/`, {
    headers: { ...headers, "Idempotency-Key": `s32ap-open-${suffix}` },
    data: { location_id: location.id },
  });
  expect(opened.ok(), await opened.text()).toBeTruthy();
  const countId = ((await opened.json()) as { id: string }).id;
  const duringCount = await page.request.post(`${API}/api/v1/inventory/receipts/`, {
    headers: { ...headers, "Idempotency-Key": `s32ap-during-${suffix}` },
    data: {
      receipt_no: `GRN-S32AP-DURING-${suffix}`,
      lines: [
        {
          product_id: product.id,
          location_id: location.id,
          batch_no: `B-S32AP-DURING-${suffix}`,
          expiry_date: new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10),
          quantity: "5.00",
        },
      ],
    },
  });
  expect(duringCount.ok(), await duringCount.text()).toBeTruthy();
  const sheet = (await (
    await page.request.get(`${API}/api/v1/inventory/counts/${countId}/`, { headers })
  ).json()) as { version: number; lines: Array<{ id: string }> };
  const submitted = await page.request.post(
    `${API}/api/v1/inventory/counts/${countId}/submit/`,
    {
      headers: { ...headers, "Idempotency-Key": `s32ap-submit-${suffix}` },
      data: {
        expected_version: sheet.version,
        lines: sheet.lines.map((line) => ({ line_id: line.id, counted_qty: "95.00" })),
      },
    }
  );
  expect(submitted.ok(), await submitted.text()).toBeTruthy();

  await signInAs(page, "admin@clinicopus.local", "ClinicopusDemo123!");
  await page.goto("/inventory");
  await expect(page.getByText("Count review", { exact: true })).toBeVisible();
  const countRow = page
    .getByRole("listitem")
    .filter({ hasText: `S32 approver store ${suffix}` })
    .first();
  await expect(countRow).toBeVisible();
  await countRow.getByRole("button", { name: "Review count", exact: true }).click();
  await expect(page.getByText(/variance -5\.00/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Movements during count/ })).toBeVisible();
  const detail = (await (
    await page.request.get(`${API}/api/v1/inventory/counts/${countId}/?reveal=1`, { headers })
  ).json()) as {
    movements_during_count: Array<{ id: string; movement_type: string }>;
  };
  expect(detail.movements_during_count.length).toBeGreaterThan(0);
  expect(
    detail.movements_during_count.some((movement) => movement.movement_type === "ADJUSTMENT")
  ).toBe(false);
});

test("S-35 Fix 4 a changed selected location cannot alter a pending count open", async ({
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
  const firstLocation = await page.request.post(`${API}/api/v1/inventory/locations/`, {
    headers,
    data: { code: `S35-L1-${suffix}`, name: `S35 location A ${suffix}`, location_type: "STORE" },
  });
  expect(firstLocation.ok(), await firstLocation.text()).toBeTruthy();
  const secondLocation = await page.request.post(`${API}/api/v1/inventory/locations/`, {
    headers,
    data: { code: `S35-L2-${suffix}`, name: `S35 location B ${suffix}`, location_type: "STORE" },
  });
  expect(secondLocation.ok(), await secondLocation.text()).toBeTruthy();
  const firstId = ((await firstLocation.json()) as { id: string }).id;
  const secondId = ((await secondLocation.json()) as { id: string }).id;
  await page.goto("/inventory");
  const location = page.getByLabel("Location", { exact: true });
  await expect.poll(async () => location.locator("option").count(), { timeout: 15_000 }).toBeGreaterThan(1);
  await location.selectOption(firstId);

  const bodies: Array<string | null> = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/counts/open/")
    ) {
      bodies.push(request.postData());
    }
  });
  let lost = false;
  await page.route("**/api/v1/inventory/counts/open/", async (route) => {
    if (!lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "Open count", exact: true }).click();
  const review = page.getByTestId("pending-intent-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  const retry = page.getByRole("button", { name: "Retry", exact: true });
  if ((await review.getAttribute("aria-expanded")) === "false") await review.click();
  await location.selectOption(secondId);
  await retry.click();
  await expect(page.getByText(/blind sheet|Count [0-9a-f-]+/).first()).toBeVisible();
  expect(bodies).toHaveLength(2);
  expect(bodies[1]).toBe(bodies[0]);
  expect(bodies[0]).toContain(firstId);
});

test("S-35 Fix 4 a count POST success with a failed read refreshes only the read", async ({
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
  const locationResponse = await page.request.post(`${API}/api/v1/inventory/locations/`, {
    headers,
    data: { code: `S35-READ-${suffix}`, name: `S35 read location ${suffix}`, location_type: "STORE" },
  });
  expect(locationResponse.ok(), await locationResponse.text()).toBeTruthy();
  const locationId = ((await locationResponse.json()) as { id: string }).id;
  await page.goto("/inventory");
  await page.getByLabel("Location", { exact: true }).selectOption(locationId);

  let posts = 0;
  let failedRead = false;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/inventory/counts/open/")
    ) {
      posts += 1;
    }
  });
  await page.route("**/api/v1/inventory/counts/open/", async (route) => route.continue());
  await page.route(/\/api\/v1\/inventory\/counts\/[0-9a-f-]+\/$/, async (route) => {
    if (!failedRead && route.request().method() === "GET") {
      failedRead = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
      return;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "Open count", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry sheet refresh", exact: true })).toBeVisible({ timeout: 15_000 });
  expect(posts).toBe(1);
  await expect(page.getByTestId("pending-intent-review")).toHaveCount(0);
  await page.getByRole("button", { name: "Retry sheet refresh", exact: true }).click();
  await expect(page.getByText(/blind sheet|Count [0-9a-f-]+/).first()).toBeVisible();
  expect(posts).toBe(1);
});
