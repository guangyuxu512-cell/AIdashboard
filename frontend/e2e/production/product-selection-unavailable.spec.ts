import { expect, test } from '@playwright/test'
import type { SelectionObservationDto } from '../../src/features/product-selection/api/selection-read-api'

// Intercepted formal HTTP contracts only; not a live platform/DB/Electron proof.
test('Real manual submits shop-bound choices, reads chosen fallback dates and persists on refresh without resubmitting', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  let submitted = false
  const commands: unknown[] = [],
    unexpected: string[] = [],
    mockModules: string[] = []
  const scope = {
    industry_id: '7',
    category_id: '1001,1002',
    brand_type: '-1',
    price_bin: '不限',
    search_info: '',
    rank_data_type: '1',
    begin_date: '2026/10/03 00:00:00',
    end_date: '2026/10/09 00:00:00',
    date_type: '21',
    activity_id: '',
  }
  const provenance = {
    policy: 'shanghai_7d_once' as const,
    accepted_local_date: '2026-10-11',
    primary_begin: '2026-10-04',
    primary_end: '2026-10-10',
    backup_begin: '2026-10-03',
    backup_end: '2026-10-09',
    actual_window: 'backup' as const,
    fallback_reason: 'primary_business_rejection_probe' as const,
    primary_error: {
      error_code: 'DOUYIN_SELECTION_BUSINESS_REJECTED' as const,
      error_stage: 'platform_business' as const,
      platform_business_code: 621000704 as const,
    },
    rank_from: 1,
    rank_to: 10,
  }
  const run = {
    run_id: 'run-1',
    request_shop_id: 'shop-1',
    status: 'succeeded',
    result_count: 1,
    saved_count: 1,
    supplement_failed_count: 0,
    error_code: null,
    request_conditions: {
      version: 2,
      scope: {
        ...scope,
        begin_date: '2026/10/04 00:00:00',
        end_date: '2026/10/10 00:00:00',
      },
      date_plan: { backup_scope: scope },
      date_outcome: {
        state: 'backup',
        fallback_reason: provenance.fallback_reason,
        primary_error: provenance.primary_error,
      },
    },
  }
  const metric = {
    state: 'available' as const,
    retrieved_at: '2026-10-11T04:00:00Z',
    value_range: [
      { value: '0', value_type: 'int' as const, unit: 'number' },
      { value: '0', value_type: 'int' as const, unit: 'number' },
    ] as [
      { value: string; value_type: 'int'; unit: string },
      { value: string; value_type: 'int'; unit: string },
    ],
  }
  const row: SelectionObservationDto = {
    observation_id: 'observation-1',
    last_run_id: 'run-1',
    candidate_id: 'candidate-1',
    product_id: '9000000000000000001',
    platform: 'douyin',
    request_shop_id: 'shop-1',
    request_shop_name: '授权测试抖店',
    source_scope_hash: 'a'.repeat(64),
    source_context: {
      version: 1,
      platform: 'douyin',
      endpoint: 'product_rank/video_bring_good',
      business: scope,
      date_selection: provenance,
    },
    period_begin: '2026-10-03',
    period_end: '2026-10-09',
    title: '拦截契约测试商品，不是平台实测',
    image_url: null,
    source_url: null,
    merchants: [{ platform_shop_id: 'merchant-1', name: '独立测试商家' }],
    category_path: ['真实父类目', '真实子类目'],
    price_band: null,
    rank: 1,
    previous_rank: null,
    previous_checked_at: null,
    newly_on_ranking: null,
    first_seen_at: '2026-10-11T03:59:00Z',
    checked_at: '2026-10-11T03:59:00Z',
    metrics_retrieved_at: '2026-10-11T04:00:00Z',
    video_metric_ranges: {
      pay_amt: metric,
      pay_combo_cnt: metric,
      product_click_cnt: metric,
      video_cnt: metric,
    },
    first_on_shelf_date: '2025-08-17',
    bad_comment_rate_raw: '0.00205018686599039',
    bad_comment_rate_unit: 4,
    basic_info_retrieved_at: '2026-10-11T04:00:01Z',
    last_attempt_at: '2026-10-11T04:00:01Z',
    last_error_code: null,
    last_error_stage: null,
  }
  page.on('request', (request) => {
    if (request.url().includes('selection-mock-handlers'))
      mockModules.push(request.url())
  })
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path === '/api/v1/auth/me')
      data = { user_id: 'test-person', display_name: '隔离契约测试' }
    else if (path === '/api/v1/access/me/teams')
      data = [
        {
          membership_id: 'test-member',
          team_id: 'test-team',
          team_name: '测试团队',
          team_enabled: true,
          membership_enabled: true,
          role_code: 'member',
          data_scope: 'team',
        },
      ]
    else if (path === '/api/v1/access-management/me/module-access')
      data = {
        module_codes: ['product-selection', 'product-library'],
        is_super_account: false,
        is_access_administrator: false,
      }
    else if (path === '/api/v1/shops')
      data = {
        items: [
          {
            shop_id: 'shop-1',
            display_name: '授权测试抖店',
            platform: 'douyin',
            platform_shop_id: 'test-platform-shop',
            enabled: true,
            owner_user_id: null,
            note: null,
            deleted_at: null,
            created_at: '2026-10-01T00:00:00Z',
            updated_at: '2026-10-01T00:00:00Z',
            session_status: 'valid',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      }
    else if (path === '/api/v1/product-selection/capabilities')
      data = {
        execution_enabled: true,
        manual_execution_available: true,
        unavailable_reason: null,
      }
    else if (path === '/api/v1/product-selection/categories') {
      expect(new URL(route.request().url()).searchParams.get('shop_id')).toBe(
        'shop-1',
      )
      data = {
        shop_id: 'shop-1',
        industry_id: '7',
        nodes: [
          {
            category_id: '5',
            name: '其它行业',
            children: [{ category_id: '5001', name: '其它类目', children: [] }],
          },
          {
            category_id: '7',
            name: '真实行业',
            children: [
              {
                category_id: '1001',
                name: '真实父类目',
                children: [
                  {
                    category_id: '1002',
                    name: '真实子类目',
                    children: [
                      {
                        category_id: '1003',
                        name: '真实四级类目',
                        children: [],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      }
    } else if (
      path === '/api/v1/product-selection/runs' &&
      route.request().method() === 'POST'
    ) {
      const command = route.request().postDataJSON()
      commands.push(command)
      submitted = true
      await route.fulfill({
        status: 202,
        json: {
          receipt_id: 'run-1',
          submission_key: command.submission_key,
          execution_run_id: 'run-1',
          reused: false,
          execution: run,
        },
      })
      return
    } else if (path === '/api/v1/product-selection/runs')
      data = {
        items: submitted ? [run] : [],
        total: submitted ? 1 : 0,
        page: 1,
        page_size: 1,
      }
    else if (path === '/api/v1/product-selection/candidates')
      data = {
        items: submitted ? [row] : [],
        total: submitted ? 1 : 0,
        page: 1,
        page_size: 10,
      }
    else if (path === '/api/v1/product-selection/observations/observation-1')
      data = row
    else {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: data })
  })
  await page.goto('/#/product-selection?tab=selection-strategy')
  // Use the existing query navigation instead of inventing a new route.
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '选品策略', exact: true })
    .click()
  await expect(
    page.getByRole('textbox', { name: '搜索策略名称' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '达人登录', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '新建策略', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  await expect(drawer.getByRole('textbox', { name: '策略名称' })).toBeVisible()
  await drawer
    .getByRole('textbox', { name: '策略名称' })
    .fill('未保存的真实条件草稿')
  await expect(
    drawer.getByRole('button', { name: '保存策略', exact: true }),
  ).toBeDisabled()
  await drawer.locator('.n-base-selection').first().click()
  await page.getByText('授权测试抖店', { exact: true }).last().click()
  await drawer.locator('.n-cascader .n-base-selection').click()
  await page.getByText('真实行业', { exact: true }).last().click()
  await page.getByText('真实父类目', { exact: true }).last().click()
  await page.getByText('真实子类目', { exact: true }).last().click()
  await page
    .locator('.n-cascader-submenu')
    .last()
    .getByText('全部', { exact: true })
    .click()
  await expect(drawer.locator('.n-cascader')).toContainText('真实子类目 / 全部')
  const schedule = drawer.locator('.n-form-item').filter({
    has: page.locator('.n-form-item-label', { hasText: /^定时执行$/ }),
  })
  await schedule.getByRole('switch').click()
  await expect(drawer.getByText('执行频率', { exact: true })).toBeVisible()
  await page.screenshot({
    path: info.outputPath('real-restored-strategy-before-submit.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText(/2026-10-03～2026-10-09 · 已回退一天/),
  ).toBeVisible()
  expect(commands).toHaveLength(1)
  expect(commands[0]).toMatchObject({
    shop_id: 'shop-1',
    industry_id: '7',
    category_ids: ['1001', '1002'],
    channel: 'short-video',
    period: '7d',
    rank_from: 1,
    rank_to: 10,
    brand: 'all',
    price_mode: 'all',
  })
  expect(commands[0]).not.toHaveProperty('begin_date')
  expect(commands[0]).not.toHaveProperty('scheduled')
  expect(commands[0]).not.toHaveProperty('name')
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '候选池', exact: true })
    .click()
  await expect(page.getByText(row.title!, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '详情', exact: true }).click()
  await expect(
    page
      .locator('.n-drawer')
      .getByText('2026-10-03～2026-10-09', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.n-drawer').getByText(/已回退一天/)).toBeVisible()
  await page.screenshot({
    path: info.outputPath('real-intercepted-fallback-detail.png'),
    animations: 'disabled',
  })
  await page
    .locator('.n-drawer')
    .getByRole('button', { name: '关闭', exact: true })
    .click()
  await page.reload()
  await expect(page.getByText(row.title!, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '刷新列表', exact: true }).click()
  expect(commands).toHaveLength(1)
  expect(mockModules).toEqual([])
  expect(unexpected).toEqual([])
})

test('Real keeps unavailable state without Mock fallback and retains route permission guard', async ({
  page,
}, info) => {
  let allowed = true
  const unexpected: string[] = []
  const runtimeErrors: string[] = []
  const mockModules: string[] = []
  let readFailed = false
  page.on('request', (request) => {
    if (request.url().includes('selection-mock-handlers'))
      mockModules.push(request.url())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  // Match the API root, not Vite's /src/shared/api/*.ts modules.
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/product-selection/candidates') {
      await route.fulfill(
        readFailed
          ? {
              status: 502,
              json: {
                code: 'PLATFORM_RESPONSE_INVALID',
                message: '查询失败测试',
                request_id: 'test-only',
              },
            }
          : { json: { items: [], total: 0, page: 1, page_size: 10 } },
      )
      return
    }
    if (path === '/api/v1/shops') {
      await route.fulfill({
        json: { items: [], total: 0, page: 1, page_size: 20 },
      })
      return
    }
    if (path === '/api/v1/product-selection/runs') {
      await route.fulfill({
        json: { items: [], total: 0, page: 1, page_size: 1 },
      })
      return
    }
    if (path === '/api/v1/product-selection/capabilities') {
      await route.fulfill({
        json: {
          execution_enabled: false,
          manual_execution_available: false,
          unavailable_reason: 'EXECUTION_DISABLED',
        },
      })
      return
    }
    const response =
      path === '/api/v1/auth/me'
        ? { user_id: 'test-person', display_name: '隔离前端验证' }
        : path === '/api/v1/access/me/teams'
          ? [
              {
                membership_id: 'test-member',
                team_id: 'test-team',
                team_name: '测试团队',
                team_enabled: true,
                membership_enabled: true,
                role_code: 'member',
                data_scope: 'team',
              },
            ]
          : path === '/api/v1/access-management/me/module-access'
            ? {
                module_codes: allowed
                  ? ['product-selection', 'product-library']
                  : ['product-library'],
                is_super_account: false,
                is_access_administrator: false,
              }
            : null
    if (!response) {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: response })
  })
  await page.goto('/#/product-selection')
  await expect.poll(() => runtimeErrors).toEqual([])
  await expect(
    page.getByText('尚未获取候选，请在选品策略中执行手动选品', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '批量采集资料', exact: true }),
  ).toBeDisabled()
  readFailed = true
  await page.getByRole('button', { name: '刷新列表', exact: true }).click()
  await expect(page.getByText('查询失败测试', { exact: true })).toBeVisible()
  await expect(page.getByText('暂无候选商品', { exact: true })).toHaveCount(0)
  await expect(page.getByText('演示商品 1', { exact: true })).toHaveCount(0)
  await expect(page.getByText('演示数据', { exact: true })).toHaveCount(0)
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '选品策略', exact: true })
    .click()
  await expect(
    page.getByText('此环境手动获取未启用，已入库结果仍可查询', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '新建策略', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '新建策略', exact: true }).click()
  await expect(
    page
      .locator('.n-drawer')
      .getByRole('button', { name: '立即获取', exact: true }),
  ).toBeDisabled()
  await expect(
    page
      .locator('.n-drawer')
      .getByRole('button', { name: '保存策略', exact: true }),
  ).toBeDisabled()
  await expect(
    page.locator('.n-drawer').getByText('定时执行', { exact: true }),
  ).toBeVisible()
  await page
    .locator('.n-drawer')
    .getByRole('button', { name: '取消', exact: true })
    .click()
  await expect(page.getByText(/Mock 示例区间/)).toHaveCount(0)
  expect(mockModules).toEqual([])
  await page.screenshot({
    path: info.outputPath('real-unavailable.png'),
    animations: 'disabled',
  })
  expect(unexpected).toEqual([])
  allowed = false
  await page.reload()
  await expect(page).toHaveURL(/permission-denied/)
  expect(unexpected).toEqual([])
})
