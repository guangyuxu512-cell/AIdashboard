import { defineConfig } from '@playwright/test'

// Serve the already-built Real bundle via request interception: no listener,
// Backend, database, external image request, or paid generation is involved.
process.env.PLAYWRIGHT_API_MODE = 'real'
process.env.PLAYWRIGHT_AI_STATIC = '1'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'ai-workbench-real-api.spec.ts',
  grep: /image proportions:|keeps a thumbnail visible|shows an explicit retry/,
  workers: 1,
  timeout: 60_000,
  outputDir: './test-results/ai-image-proportions',
  use: {
    baseURL: 'https://ai-images.test',
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
  },
})
