import { defineConfig } from '@playwright/test'

const apiMode = process.env.PLAYWRIGHT_API_MODE === 'real' ? 'real' : 'mock'
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT ?? '8000'
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '4173'

const productionTestFiles = ['**/production/**']
const realTestFiles = [
  '**/auth-real.spec.ts',
  '**/real-api.spec.ts',
  '**/ai-workbench-real-backend.spec.ts',
]
const visualTestFiles = [
  '**/ai-assets.spec.ts',
  '**/ai-generation.spec.ts',
  '**/ai-templates.spec.ts',
  '**/home.spec.ts',
]

export default defineConfig({
  testDir: './e2e',
  projects:
    apiMode === 'real'
      ? [
          {
            name: 'real',
            testMatch: realTestFiles,
          },
        ]
      : [
          {
            name: 'mock',
            testIgnore: [
              ...productionTestFiles,
              ...realTestFiles,
              ...visualTestFiles,
            ],
          },
          {
            name: 'visual',
            testMatch: visualTestFiles,
          },
        ],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
  },
  webServer: [
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${frontendPort} --strictPort --mode ${apiMode}`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      env: {
        VITE_API_MODE: apiMode,
        ...(apiMode === 'real'
          ? { VITE_API_PROXY_TARGET: `http://127.0.0.1:${backendPort}` }
          : {}),
      },
    },
    ...(apiMode === 'real'
      ? [
          {
            command: `".venv\\Scripts\\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
            cwd: '../backend',
            url: `http://127.0.0.1:${backendPort}/health`,
            reuseExistingServer: false,
          },
        ]
      : []),
  ],
})
