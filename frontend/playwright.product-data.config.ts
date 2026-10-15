import { defineConfig } from '@playwright/test'

const mode = process.env.PRODUCT_DATA_API_MODE === 'real' ? 'real' : 'mock'
const port = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '4177'
// Only the assigned frontend port; no Backend, DB seed or Electron process.
export default defineConfig({
  testDir: './e2e',
  testMatch:
    mode === 'real'
      ? 'production/product-data-unavailable.spec.ts'
      : ['product-data.spec.ts', 'product-data-title.spec.ts'],
  workers: 1,
  outputDir: 'test-results/product-data-' + mode,
  use: {
    screenshot: 'only-on-failure',
    timezoneId: 'Asia/Shanghai',
    baseURL: 'http://127.0.0.1:' + port,
    permissions: ['clipboard-read', 'clipboard-write'],
  },
  webServer: {
    command:
      'pnpm exec vite --host 127.0.0.1 --port ' +
      port +
      ' --strictPort --mode ' +
      mode,
    url: 'http://127.0.0.1:' + port,
    reuseExistingServer:
      mode === 'mock' && process.env.PRODUCT_DATA_REUSE_PREVIEW === '1',
    env: { VITE_API_MODE: mode },
  },
})
