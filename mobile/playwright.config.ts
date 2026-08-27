import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  testIgnore: '**/visual-preview.spec.ts',
  fullyParallel: true,
  use: {
    baseURL: 'http://127.0.0.1:4174',
    hasTouch: true,
    isMobile: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm exec vite --host 127.0.0.1 --port 4174',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
  },
})
