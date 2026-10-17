import { mergeConfig } from 'vitest/config'
import original from './vitest.config'

const config = mergeConfig(original, {
  envDir: process.env.VERIFY_EMPTY_ENV_DIR,
  test: {
    include: ['tests/contracts/**/*.spec.ts'],
    env: { VITE_API_MODE: 'real' },
  },
})
// mergeConfig concatenates include arrays; this probe must not run the entire
// existing unit suite or treat its Mock environment as Real.
config.test!.include = ['tests/contracts/**/*.spec.ts']
export default config
