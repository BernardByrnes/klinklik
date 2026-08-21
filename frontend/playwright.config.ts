import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  workers: 1,
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "npm run dev -- --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8100" },
    },
    {
      command: "python ../backend/manage.py runserver 8100 --noreload",
      url: "http://127.0.0.1:8100/api/v1/health/",
      reuseExistingServer: false,
      timeout: 120_000,
      env: { FRONTEND_ORIGIN: "http://127.0.0.1:3100" },
    },
  ],
});
