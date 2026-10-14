import { defineConfig } from "../../frontend/node_modules/@playwright/test";
import { existsSync } from "node:fs";

const systemBrowser =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  timeout: 45000,
  expect: { timeout: 15000 },
  workers: 1,
  retries: 0,
  outputDir: "../../test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../../playwright-report", open: "never" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 1000 },
    launchOptions: { executablePath: systemBrowser },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
