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
          worker_runtime: { connection_status: 'online' }, shops: Array.from({ length: 5 }, (_, index) => ({
            local_shop_id: `local-${index + 1}`, platform_shop_id: `123${index + 1}`, shop_name: `示例店铺${index + 1}`, platform: 'douyin',
            session_status: 'valid', status_observed_at: '2026-11-23T05:00:00Z',
            compass_session_status: 'unknown', compass_status_observed_at: null,
          })),
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
    '/product-data',
  ]) {
    await page.goto(`/#${oldPath}`)
    await expect(page).toHaveURL(/#\/devices$/)
    const nav = page.getByRole('navigation', { name: '主导航', exact: true })
    await expect(nav).toBeVisible()
    await expect(nav.getByText('AI 工作台', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('AI 素材', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('商品库', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('选品库', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('商品数据', { exact: true })).toHaveCount(0)
    await expect(nav.getByText('自动化中心', { exact: true })).toBeVisible()
  }

  await page.goto('/#/worker-shops')
  await expect(page.getByText('共 5 条', { exact: true })).toBeVisible()
  const body = page.locator('.n-data-table-base-table-body')
  const firstRow = page.getByRole('row', { name: /示例店铺1/ })
  const lastRow = page.getByRole('row', { name: /示例店铺5/ })
  await expect(firstRow).toContainText('设备一')
  await expect(firstRow).toContainText('有效')
  await expect(firstRow).toContainText('未确认')
  await expect(page.getByText('罗盘验证时间', { exact: true })).toBeVisible()
  for (const size of [{ width: 1440, height: 1000 }, { width: 1366, height: 768 }]) {
    await page.setViewportSize(size)
    await expect.poll(async () => {
      const bodyBox = await body.boundingBox()
      const firstBox = await firstRow.boundingBox()
      const lastBox = await lastRow.boundingBox()
      return Boolean(bodyBox && firstBox && lastBox &&
        bodyBox.height >= lastBox.y + lastBox.height - firstBox.y &&
        firstBox.y >= bodyBox.y && lastBox.y + lastBox.height <= bodyBox.y + bodyBox.height)
    }).toBe(true)
  }
  const search = page.getByPlaceholder('搜索店铺或设备')
  await search.fill('示例店铺3')
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
  await expect(page.getByRole('row', { name: /示例店铺3/ })).toHaveCount(1)
  await search.clear()
  await expect(page.getByText('共 5 条', { exact: true })).toBeVisible()

})
