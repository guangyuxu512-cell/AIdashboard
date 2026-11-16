import { fileURLToPath } from 'node:url'

import { defineConfig } from '@playwright/test'

const mobileRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  testDir: './tests/production',
  outputDir: 'test-results/production-pwa',
  fullyParallel: false,
  use: {
    baseURL: 'http://127.0.0.1:4176',
    hasTouch: true,
    isMobile: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      'pnpm run build && pnpm exec vite preview --host 127.0.0.1 --port 4176 --strictPort',
    cwd: mobileRoot,
    url: 'http://127.0.0.1:4176/mobile/',
    reuseExistingServer: false,
  },
})
