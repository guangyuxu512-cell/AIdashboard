import { defineConfig } from '@playwright/test'

// Exercise the built Real renderer with intercepted responses; no listener or
// production data is used by this check.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'execution-navigation-real-bundle.spec.ts',
  workers: 1,
  timeout: 60_000,
  outputDir: './test-results/execution-navigation',
  use: {
    baseURL: 'https://execution-navigation.test',
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
  },
})
