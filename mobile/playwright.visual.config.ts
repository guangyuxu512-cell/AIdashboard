import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /visual-(preview|token-tuner)\.spec\.ts/,
  outputDir: 'test-results/visual-preview',
  fullyParallel: true,
  use: {
    baseURL: 'http://127.0.0.1:4175',
    hasTouch: true,
    isMobile: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      'pnpm exec vite --mode visual --host 127.0.0.1 --port 4175 --strictPort',
    url: 'http://127.0.0.1:4175',
    reuseExistingServer: false,
  },
})
