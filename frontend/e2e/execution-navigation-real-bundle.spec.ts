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
            'settings',
          ],
          is_super_account: true,
          is_access_administrator: true,
        },
        '/api/v1/devices': { items: [], total: 0, page: 1, page_size: 20 },
        '/api/v1/devices/local-shop-overview': [{
          device_id: '00000000-0000-4000-8000-000000000091', device_name: '设备一',
          device_enabled: true, available: true, last_discovered_at: '2026-11-23T05:00:00Z',
          worker_runtime: { connection_status: 'online' }, shops: [{
            local_shop_id: 'local-1', platform_shop_id: '123', shop_name: '示例店铺', platform: 'douyin',
            session_status: 'valid', status_observed_at: '2026-11-23T05:00:00Z',
            compass_session_status: 'unknown', compass_status_observed_at: null,
          }],
        }],
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
    '/product-selection',
  ]) {
    await page.goto(`/#${oldPath}`)
    await expect(page).toHaveURL(/#\/devices$/)
    const nav = page.getByRole('navigation', { name: '主导航', exact: true })
    await expect(nav).toBeVisible()
    await expect(nav.getByText('AI 工作台', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('AI 素材', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('商品库', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('选品库', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('自动化中心', { exact: true })).toBeVisible()
  }

  await page.goto('/#/worker-shops')
  await expect(page.getByText('示例店铺', { exact: true })).toBeVisible()
  await expect(page.getByText('设备一', { exact: true })).toBeVisible()
  await expect(page.getByText('有效', { exact: true })).toBeVisible()
  await expect(page.getByText('未确认', { exact: true })).toBeVisible()
  await expect(page.getByText('罗盘验证时间', { exact: true })).toBeVisible()

})
