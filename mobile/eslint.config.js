import pluginVue from 'eslint-plugin-vue'
import {
  defineConfigWithVueTs,
  vueTsConfigs,
} from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  {
    files: ['src/pages/**/*.{ts,vue}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'axios',
              message:
                'Page 禁止直接调用 Axios；请通过 Entity API/DataSource。',
            },
          ],
          patterns: [
            {
              group: ['@/shared/api', '@/shared/api/*'],
              message:
                'Page 禁止绕过 Entity API/DataSource 访问共享 API Client。',
            },
          ],
        },
      ],
    },
  },
  skipFormatting,
)
