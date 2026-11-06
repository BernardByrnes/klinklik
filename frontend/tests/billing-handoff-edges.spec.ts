import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "ClinicopusDemo!2026";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

type ApiSession = {
  access_token: string;
  facilities: Array<{ id: string }>;
};

type CheckInResult = {
  visit_id: string;
  invoice_id: string | null;
};

async function signIn(page: Page) {
  const response = await page.request.post(`${API}/api/v1/auth/login/`, {
    data: { username: "demo", password: DEMO_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as ApiSession;
}

function apiHeaders(session: ApiSession) {
  return {
    Authorization: `Bearer ${session.access_token}`,
    "X-Facility-Id": session.facilities[0].id,
    "Content-Type": "application/json",
  };
}

async function newChargeableVisit(page: Page, session: ApiSession, label: string) {
  const suffix = `${Date.now().toString().slice(-6)}${Math.trunc(Math.random() * 1000)}`;
  const patient = await page.request.post(`${API}/api/v1/patients/`, {
    headers: apiHeaders(session),
    data: {
      first_name: label,
      last_name: `Edge${suffix}`,
      sex: "FEMALE",
      phone: `07${suffix.slice(-8).padStart(8, "0")}`,
    },
  });
  expect(patient.ok()).toBeTruthy();
  const patientId = ((await patient.json()) as { id: string }).id;

  const checkIn = await page.request.post(`${API}/api/v1/reception/visits/check-in/`, {
    headers: { ...apiHeaders(session), "Idempotency-Key": `edge-checkin-${suffix}` },
    data: { patient_id: patientId, visit_type: "OUTPATIENT_NEW", payer_type: "CASH" },
  });
  expect(checkIn.ok()).toBeTruthy();
  const result = (await checkIn.json()) as CheckInResult;
  expect(result.invoice_id).toBeTruthy();
  return { visitId: result.visit_id, invoiceId: result.invoice_id as string };
}

async function readInvoice(page: Page, invoiceId: string) {
  // The page rotates the session token when it restores, so verification takes
  // its own token from the shared refresh cookie.
  const refreshed = await page.request.post(`${API}/api/v1/auth/refresh/`);
  if (!refreshed.ok()) {
    throw new Error(`Session refresh failed: ${refreshed.status()}`);
  }
  const session = (await refreshed.json()) as ApiSession;
  const response = await page.request.get(`${API}/api/v1/billing/invoices/${invoiceId}/`, {
    headers: apiHeaders(session),
  });
  if (!response.ok()) {
    throw new Error(
      `Invoice read failed: ${response.status()} ${await response.text()} (${invoiceId})`,
    );
  }
  return (await response.json()) as {
    status: string;
    amount_paid: string;
    balance: string;
    payments: Array<{ id: string; amount: string }>;
  };
}

function countPaymentPosts(page: Page) {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/pay/")) {
      posts.push(request.url());
    }
  });
  return posts;
}

test("a failed receipt never reads as a failed payment", async ({ page }) => {
  const session = await signIn(page);
  const { visitId, invoiceId } = await newChargeableVisit(page, session, "Partial");

  const paymentPosts = countPaymentPosts(page);
  let failReceipt = true;
  await page.route(/\/api\/v1\/billing\/invoices\/[^/]+\/receipt\/$/, async (route) => {
    if (failReceipt) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Receipt temporarily unavailable." }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto(`/billing?visit=${visitId}`);
  await expect(page.getByRole("heading", { name: "Visit invoice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toBeVisible();

  const amount = page.getByLabel(/^Amount \(/);
  await amount.fill("10000");
  await page.getByRole("button", { name: "Post payment" }).click();

  // The payment POST committed; only the receipt read failed.
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Payment recorded, but the receipt could not be loaded." }),
  ).toBeVisible();
  await expect(page.getByText("Payment recorded.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry receipt" })).toBeVisible();
  // The old submission stays out of the UI while the posted result reconciles.
  await expect(page.getByRole("button", { name: "Post payment" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Receipt" })).toHaveCount(0);
  expect(paymentPosts).toHaveLength(1);

  failReceipt = false;
  await page.getByRole("button", { name: "Retry receipt" }).click();
  const receiptCard = page.locator("[data-print-sheet]");
  await expect(receiptCard).toBeVisible();
  await expect(receiptCard).toContainText("Receipt");
  await expect(page.getByText(/Payment recorded\. Receipt RCT-/)).toBeVisible();
  expect(paymentPosts).toHaveLength(1);

  // An explicit new collection starts from the refreshed balance.
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByRole("button", { name: "Post payment" })).toBeVisible();
  await expect(page.getByLabel(/^Amount \(/)).toHaveValue("20000.00");

  // Verified last: taking a token for this read rotates the page's session.
  const settled = await readInvoice(page, invoiceId);
  expect(settled.payments).toHaveLength(1);
  expect(settled.amount_paid).toBe("10000.00");
  expect(settled.balance).toBe("20000.00");
});

test("a delayed receipt cannot land on another Visit", async ({ page }) => {
  const session = await signIn(page);
  const first = await newChargeableVisit(page, session, "SwitchA");
  const second = await newChargeableVisit(page, session, "SwitchB");

  await page.goto(`/billing?visit=${first.visitId}`);
  await expect(page.getByRole("heading", { name: "Visit invoice" })).toBeVisible();

  let releaseReceipt: (() => Promise<void>) | null = null;
  await page.route(/\/api\/v1\/billing\/invoices\/[^/]+\/receipt\/$/, async (route) => {
    await new Promise<void>((resolve) => {
      releaseReceipt = async () => {
        try {
          await route.continue();
        } finally {
          resolve();
        }
      };
    });
  });

  const amount = page.getByLabel(/^Amount \(/);
  await expect(amount).not.toHaveValue("");
  await page.getByRole("button", { name: "Post payment" }).click();
  await expect(page.getByText("Payment recorded. Preparing the receipt.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toHaveCount(0);

  // Switch the same mounted workspace to the other Visit, without a reload.
  await page.evaluate((visitId) => {
    window.history.pushState({}, "", `/billing?visit=${visitId}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, second.visitId);
  await expect(page).toHaveURL(new RegExp(`/billing\\?visit=${second.visitId}`));
  await expect(page.getByRole("button", { name: "Post payment" })).toBeVisible();
  await expect(page.getByText(/SwitchB/).first()).toBeVisible();

  // Release the first Visit's receipt after the switch.
  expect(releaseReceipt).not.toBeNull();
  await releaseReceipt!();
  await page.waitForTimeout(500);

  await expect(page.getByText(/SwitchB/).first()).toBeVisible();
  await expect(page.getByText(/SwitchA/)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Receipt" })).toHaveCount(0);
  await expect(page.getByText(/Payment recorded\. Receipt RCT-/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Post payment" })).toBeVisible();
});

test("a malformed Visit link never opens an invoice for payment", async ({ page }) => {
  const session = await signIn(page);
  const { visitId, invoiceId } = await newChargeableVisit(page, session, "Link");

  const lookups: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/billing/invoices/")) lookups.push(request.url());
  });

  await page.goto("/billing?visit=");
  await expect(page.getByText("This billing link does not identify a Visit.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create invoice" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "New invoice" })).toHaveCount(0);
  expect(lookups).toEqual([]);

  await page.goto(`/billing?visit=${encodeURIComponent(`../${invoiceId}`)}`);
  await expect(page.getByText("This billing link does not identify a Visit.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toHaveCount(0);
  // The traversal value must never reach the invoice-detail route.
  expect(lookups).toEqual([]);

  // A well-formed Visit that has no payable invoice is unavailable, not payable.
  await page.goto(`/billing?visit=${"0".repeat(8)}-0000-4000-8000-${"0".repeat(12)}`);
  await expect(page.getByText("No payable invoice exists for this Visit.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toHaveCount(0);

  // A valid Visit still opens its original invoice.
  await page.goto(`/billing?visit=${visitId}`);
  await expect(page.getByRole("heading", { name: "Visit invoice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Post payment" })).toBeVisible();
  expect(lookups.some((url) => url.includes(`/invoices/by-visit/${visitId}/`))).toBe(true);
});
