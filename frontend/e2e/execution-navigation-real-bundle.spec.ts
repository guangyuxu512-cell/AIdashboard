import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import { expect, test } from '@playwright/test'

test('the Real bundle keeps execution navigation and removes retired pages', async ({
  page,
}) => {
  const dist = resolve('dist')
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.origin !== 'https://execution-navigation.test') {
      await route.abort()
      return
    }
    if (url.pathname.startsWith('/api/')) {
      const data: Record<string, unknown> = {
        '/api/v1/auth/me': {
          user_id: '00000000-0000-4000-8000-000000000001',
          display_name: '测试管理员',
        },
        '/api/v1/access/me/teams': [
          {
            membership_id: null,
            team_id: '00000000-0000-4000-8000-000000000021',
            team_name: '测试团队',
            team_enabled: true,
            role_code: 'super_account',
            data_scope: 'all',
            membership_enabled: true,
          },
        ],
        '/api/v1/access-management/me/module-access': {
          module_codes: [
            'device',
            'task',
            'schedule',
            'shop',
            'asset',
            'product-selection',
            'settings',
          ],
          is_super_account: true,
          is_access_administrator: true,
        },
        '/api/v1/devices': { items: [], total: 0, page: 1, page_size: 20 },
      }
      await route.fulfill({ json: data[url.pathname] ?? [] })
      return
    }
    const file = resolve(
      dist,
      `.${decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname)}`,
    )
    if (!file.startsWith(`${dist}${sep}`))
      throw new Error('Invalid static asset path')
    const extension = file.split('.').at(-1) ?? ''
    const contentType =
      (
        {
          html: 'text/html',
          js: 'text/javascript',
          css: 'text/css',
          svg: 'image/svg+xml',
          png: 'image/png',
          woff2: 'font/woff2',
        } as Record<string, string>
      )[extension] ?? 'application/octet-stream'
    await route.fulfill({ contentType, body: await readFile(file) })
  })

  for (const oldPath of [
    '/ai-workbench/assets',
    '/settings/ai-models',
    '/products',
  ]) {
    await page.goto(`/#${oldPath}`)
    await expect(page).toHaveURL(/#\/devices$/)
    const nav = page.getByRole('navigation', { name: '主导航', exact: true })
    await expect(nav).toBeVisible()
    await expect(nav.getByText('AI 工作台', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('AI 素材', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('商品库', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('自动化中心', { exact: true })).toBeVisible()
  }

  await page.goto('/#/product-selection?tab=collection-tasks')
  const selectionBar = page.getByRole('navigation', {
    name: '选品库切换',
    exact: true,
  })
  await expect(
    selectionBar.getByRole('button', { name: '候选池', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    selectionBar.getByRole('button', { name: '选品策略', exact: true }),
  ).toBeVisible()
  await expect(
    selectionBar.getByRole('button', { name: '采集任务', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '批量采集资料', exact: true }),
  ).toHaveCount(0)
})
