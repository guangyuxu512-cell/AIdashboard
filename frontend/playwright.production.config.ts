import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/production',
  use: {
    baseURL: 'http://127.0.0.1:4174',
  },
  webServer: {
    command:
      'pnpm run build:visual-mock && pnpm exec vite preview --host 127.0.0.1 --port 4174',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
  },
})
