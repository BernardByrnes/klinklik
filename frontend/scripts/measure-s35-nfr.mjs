import { chromium } from "playwright";

const BASE = process.env.NFR_BASE_URL ?? "http://127.0.0.1:3102";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";
const PASSWORD = process.env.CLINICOPUS_E2E_PASSWORD ?? "ClinicopusDemo!2026";

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const client = await context.newCDPSession(page);
await client.send("Network.enable");

const resourceTypes = new Map();
let bytes = { total: 0, Script: 0, Document: 0, Stylesheet: 0, Font: 0, XHR: 0 };
client.on("Network.responseReceived", (event) => {
  resourceTypes.set(event.requestId, event.type);
});
client.on("Network.loadingFinished", (event) => {
  const size = event.encodedDataLength ?? 0;
  bytes.total += size;
  const type = resourceTypes.get(event.requestId) ?? "Other";
  bytes[type] = (bytes[type] ?? 0) + size;
});
function resetBytes() {
  bytes = { total: 0, Script: 0, Document: 0, Stylesheet: 0, Font: 0, XHR: 0 };
}

const login = await page.request.post(`${API}/api/v1/auth/login/`, {
  data: { username: "demo", password: PASSWORD },
});
if (!login.ok()) throw new Error(`login failed: ${await login.text()}`);
const setCookie = login.headers()["set-cookie"] ?? "";
const refreshPair = setCookie.split(";")[0].split("=");
if (refreshPair.length !== 2) throw new Error(`missing refresh cookie: ${setCookie}`);
await context.addCookies([
  {
    name: refreshPair[0],
    value: refreshPair[1],
    domain: "127.0.0.1",
    path: "/api/v1/auth/",
  },
]);

await client.send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 300,
  downloadThroughput: 400_000 / 8,
  uploadThroughput: 400_000 / 8,
  connectionType: "cellular3g",
});

async function waitForPatients() {
  await page.getByRole("heading", { name: "Patients", exact: true }).waitFor();
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-testid="connectivity-status"]');
    return Boolean(node && node.textContent?.includes("Patients last synced"));
  });
}

resetBytes();
let started = Date.now();
await page.goto(`${BASE}/patients`, { waitUntil: "domcontentloaded" });
await waitForPatients();
const coldMs = Date.now() - started;
const coldBytes = { ...bytes };

const warmMs = [];
const warmBytes = [];
for (let index = 0; index < 5; index += 1) {
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.waitForURL(/\/overview$/);
  resetBytes();
  started = Date.now();
  await page.getByRole("link", { name: "Patients", exact: true }).click();
  await waitForPatients();
  warmMs.push(Date.now() - started);
  warmBytes.push({ ...bytes });
}

await client.send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 0,
  downloadThroughput: -1,
  uploadThroughput: -1,
  connectionType: "none",
});

const p95 = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1)];
};

console.log(
  JSON.stringify(
    {
      profile: "400kbps,300ms",
      scope: "encoded transfer bytes by CDP resource type",
      coldMs,
      coldBytes,
      warmMs,
      warmBytes,
      warmP95Ms: p95(warmMs),
      warmP95ScriptBytes: p95(warmBytes.map((entry) => entry.Script)),
      warmP95TotalBytes: p95(warmBytes.map((entry) => entry.total)),
      api: API,
    },
    null,
    2,
  ),
);

await browser.close();
