import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3001",
    browserName: "chromium",
    headless: true,
    trace: "retain-on-failure",
  },
});
