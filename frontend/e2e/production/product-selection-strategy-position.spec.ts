import { expect, test } from '@playwright/test'
import type { SelectionStrategyDto } from '../../src/features/product-selection/api/selection-strategy-api'
import { settleSelectionTransitions as settle } from '../support/settle-selection-transitions'

// Real Renderer, fully intercepted APIs. Not live platform or Electron evidence.
test('strategy toggling and existing editing retain page, filter, order and scroll', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const rows: SelectionStrategyDto[] = Array.from(
    { length: 60 },
    (_, index) => ({
      strategy_id: `position-${index + 1}`,
      team_id: 'position-team',
      created_by_user_id: 'position-person',
      name: `稳定策略${String(index + 1).padStart(3, '0')}`,
      shop_id: 'position-shop',
      shop_name: '授权合成店铺',
      enabled: false,
      version: 1,
      conditions: {
        version: 1,
        request: {
          channel: 'short-video',
          period: '7d',
          industry_id: '7',
          category_ids: ['1001'],
          brand: 'all',
          price_mode: 'all',
          price_above: null,
          price_below: null,
          first_listed_only: false,
          rank_from: 1,
          rank_to: 10,
        },
      },
      schedule: {
        scheduled: false,
        kind: 'hourly',
        daily_time: '09:00',
        timezone: 'Asia/Shanghai',
      },
      schedule_available: false,
      next_run_at: null,
      latest_run: null,
      created_at: '2026-10-13T00:00:00Z',
      updated_at: '2026-10-13T00:00:00Z',
    }),
  )
  const listReads: { page: number; search: string }[] = []
  const unexpected: string[] = []
  let releaseToggle!: () => void
  const toggleResponse = new Promise<void>((resolve) => {
    releaseToggle = resolve
  })
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname,
      method = request.method()
    let data: unknown
    if (path === '/api/v1/auth/me')
      data = { user_id: 'position-person', display_name: '正式API拦截' }
    else if (path === '/api/v1/access/me/teams') data = []
    else if (path === '/api/v1/access-management/me/module-access')
      data = {
        module_codes: ['product-selection'],
        is_super_account: true,
        is_access_administrator: true,
      }
    else if (path === '/api/v1/shops')
      data = {
        items: [
          {
            shop_id: 'position-shop',
            display_name: '授权合成店铺',
            platform: 'douyin',
            enabled: true,
            owner_user_id: null,
            note: null,
            created_at: '2026-10-01T00:00:00Z',
            updated_at: '2026-10-01T00:00:00Z',
            deleted_at: null,
            session_status: 'valid',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      }
    else if (path === '/api/v1/product-selection/capabilities')
      data = {
        manual_execution_available: false,
        strategy_save_available: true,
        schedule_available: false,
        supported_periods: ['realtime', '7d'],
        supported_brands: ['all'],
        custom_price_available: false,
        first_listed_filter_available: true,
        max_rank: 200,
      }
    else if (path === '/api/v1/product-selection/runs' && method === 'GET')
      data = { items: [], total: 0, page: 1, page_size: 1 }
    else if (path === '/api/v1/product-selection/categories')
      data = {
        shop_id: 'position-shop',
        industry_id: '7',
        nodes: [
          {
            category_id: '7',
            name: '合成行业',
            children: [
              { category_id: '1001', name: '已确认路径合成类目', children: [] },
            ],
          },
        ],
      }
    else if (
      path === '/api/v1/product-selection/strategies' &&
      method === 'GET'
    ) {
      const current = Number(url.searchParams.get('page') ?? 1),
        size = Number(url.searchParams.get('page_size') ?? 20),
        search = url.searchParams.get('search') ?? ''
      listReads.push({ page: current, search })
      const filtered = rows.filter((row) => row.name.includes(search))
      data = {
        items: filtered.slice((current - 1) * size, current * size),
        total: filtered.length,
        page: current,
        page_size: size,
      }
    } else if (
      path.startsWith('/api/v1/product-selection/strategies/') &&
      ['PUT', 'PATCH'].includes(method)
    ) {
      const id = path.split('/')[5]!,
        index = rows.findIndex((row) => row.strategy_id === id),
        body = request.postDataJSON()
      expect(body.expected_version).toBe(rows[index]!.version)
      const { expected_version, ...saved } = body
      if (method === 'PATCH') await toggleResponse
      rows[index] = {
        ...rows[index]!,
        ...saved,
        version: expected_version + 1,
        updated_at: '2026-10-13T02:00:00Z',
      }
      data = rows[index]
    } else {
      unexpected.push(`${method} ${path}`)
      await route.abort()
      return
    }
    await route.fulfill({ json: data })
  })
  await page.goto('/#/product-selection?tab=selection-strategy')
  await expect(page.getByText('稳定策略001', { exact: true })).toBeVisible()
  const search = page.getByRole('textbox', { name: '搜索策略名称' })
  await search.fill('稳定策略')
  await search.press('Enter')
  await page
    .locator('.n-pagination-item')
    .getByText('2', { exact: true })
    .click()
  await expect(page.getByText('稳定策略021', { exact: true })).toBeVisible()
  const body = page
    .locator('.n-data-table-base-table-body .n-scrollbar-container')
    .first()
  await body.evaluate((element) => {
    element.scrollTop = 120
    // Show status cells fully, outside the sticky action column's overlay.
    element.scrollLeft = element.scrollWidth - element.clientWidth
  })
  const targetName = '稳定策略027'
  const target = () =>
    page
      .locator('.n-data-table-base-table-body .n-data-table-tr')
      .filter({ hasText: targetName })
      .first()
  const state = () =>
    body.evaluate((element) => ({
      top: element.scrollTop,
      left: element.scrollLeft,
    }))
  const ids = () =>
    page
      .locator('.n-data-table-base-table-body .n-data-table-tr')
      .allTextContents()
  // Ensure the target is fully visible before measuring. Playwright otherwise
  // legitimately scrolls an overlapped/off-screen control before the click.
  await page
    .getByRole('switch', { name: `${targetName}启用状态` })
    .scrollIntoViewIfNeeded()
  const before = await state(),
    beforeIds = await ids()
  await page.getByRole('switch', { name: `${targetName}启用状态` }).click()
  expect(await state()).toEqual(before)
  releaseToggle()
  await expect(
    page.getByRole('switch', { name: `${targetName}启用状态` }),
  ).toHaveAttribute('aria-checked', 'true')
  await expect
    .poll(() => listReads.at(-1))
    .toEqual({ page: 2, search: '稳定策略' })
  expect(await ids()).toEqual(beforeIds)
  expect(await state()).toEqual(before)
  await target().getByRole('button', { name: '编辑', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  await drawer
    .getByRole('textbox', { name: '策略名称' })
    .fill(`${targetName}已编辑`)
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(drawer).toBeHidden()
  await settle(page)
  await expect(
    page.getByText(`${targetName}已编辑`, { exact: true }),
  ).toBeVisible()
  expect(listReads.at(-1)).toEqual({ page: 2, search: '稳定策略' })
  expect(await state()).toEqual(before)
  await expect(search).toHaveValue('稳定策略')
  expect(rows[26]!.version).toBe(3)
  expect(rows[26]!.enabled).toBe(true)
  expect(rows[26]!.updated_at).toBe('2026-10-13T02:00:00Z')
  expect(unexpected).toEqual([])
})
