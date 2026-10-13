import { expect, test } from '@playwright/test'
import type {
  SelectionStrategyDto,
  SelectionStrategyWriteDto,
} from '../../src/features/product-selection/api/selection-strategy-api'
import { settleSelectionTransitions as settle } from '../support/settle-selection-transitions'

// Real Renderer with fully intercepted formal APIs. Synthetic configuration and
// run responses are not live platform, persisted DB, or native Electron proof.
for (const period of ['7d', 'realtime', '1d', '30d'] as const) {
  test(`${period}: saved strategies keep the original UI, CAS editing, and independent immediate retrieval`, async ({
    page,
  }, info) => {
    test.setTimeout(120000)
    await page.setViewportSize({ width: 1440, height: 900 })
    const otherIndustry = ['realtime', '30d'].includes(period)
    const industryId = otherIndustry ? '41' : '7'
    const categoryId = otherIndustry ? '4101' : '1001'
    const industryLabel = otherIndustry ? '合成非默认行业' : '合成行业'
    const categoryLabel = otherIndustry ? '其它父类目' : '父级类目'
    let strategy: SelectionStrategyDto | null = null
    const writes: {
      method: string
      path: string
      body: Record<string, unknown>
    }[] = []
    const unexpected: string[] = [],
      mocks: string[] = []
    let run: Record<string, unknown> | null = null
    let rejectToggle = true
    page.on('request', (request) => {
      if (request.url().includes('selection-mock-handlers'))
        mocks.push(request.url())
    })
    await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
      const request = route.request(),
        path = new URL(request.url()).pathname,
        method = request.method()
      let data: unknown
      if (method !== 'GET')
        writes.push({ method, path, body: request.postDataJSON() })
      if (path === '/api/v1/auth/me')
        data = { user_id: 'strategy-person', display_name: 'API拦截验证' }
      else if (path === '/api/v1/access/me/teams')
        data = [
          {
            membership_id: 'strategy-member',
            team_id: 'strategy-team',
            team_name: '隔离验证团队',
            team_enabled: true,
            membership_enabled: true,
            role_code: 'member',
            data_scope: 'team',
          },
        ]
      else if (path === '/api/v1/access-management/me/module-access')
        data = {
          module_codes: ['product-selection'],
          is_super_account: false,
          is_access_administrator: false,
        }
      else if (path === '/api/v1/shops')
        data = {
          items: [
            {
              shop_id: 'strategy-shop',
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
          execution_enabled: true,
          manual_execution_available: true,
          unavailable_reason: null,
          strategy_save_available: true,
          schedule_available: false,
          supported_periods: ['realtime', '1d', '7d', '30d'],
          supported_brands: ['all'],
          custom_price_available: false,
          first_listed_filter_available: true,
          max_rank: 200,
        }
      else if (path === '/api/v1/product-selection/categories')
        data = {
          shop_id: 'strategy-shop',
          industry_id: '7',
          industry_name: '实际树合成对照',
          selected_category_id: null,
          nodes: [
            {
              category_id: '41',
              name: '合成非默认行业',
              children: [
                {
                  category_id: '4101',
                  name: '其它父类目',
                  children: [
                    { category_id: '4102', name: '其它子类目', children: [] },
                  ],
                },
              ],
            },
            {
              category_id: '7',
              name: '合成行业',
              children: [
                {
                  category_id: '1001',
                  name: '父级类目',
                  children: [
                    { category_id: '1002', name: '子级类目', children: [] },
                  ],
                },
              ],
            },
          ],
        }
      else if (
        path === '/api/v1/product-selection/strategies' &&
        method === 'GET'
      )
        data = {
          items: strategy ? [strategy] : [],
          total: strategy ? 1 : 0,
          page: 1,
          page_size: 20,
        }
      else if (
        path === '/api/v1/product-selection/strategies' &&
        method === 'POST'
      ) {
        const body = request.postDataJSON() as SelectionStrategyWriteDto
        strategy = {
          ...body,
          strategy_id: 'saved-strategy',
          team_id: 'strategy-team',
          created_by_user_id: 'strategy-person',
          shop_name: '授权合成店铺',
          version: 1,
          schedule_available: false,
          next_run_at: null,
          latest_run: null,
          created_at: '2026-10-13T00:00:00Z',
          updated_at: '2026-10-13T00:00:00Z',
        }
        await route.fulfill({ status: 201, json: strategy })
        return
      } else if (
        path === '/api/v1/product-selection/strategies/saved-strategy' &&
        method === 'PUT'
      ) {
        const body = request.postDataJSON() as SelectionStrategyWriteDto & {
          expected_version: number
        }
        if (body.expected_version !== strategy!.version) {
          await route.fulfill({
            status: 409,
            json: {
              code: 'PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT',
              message: '策略已被修改，请刷新已保存内容；当前草稿未覆盖',
            },
          })
          return
        }
        expect(body.expected_version).toBe(strategy!.version)
        const { expected_version, ...saved } = body
        strategy = { ...strategy!, ...saved, version: expected_version + 1 }
        data = strategy
      } else if (
        path ===
          '/api/v1/product-selection/strategies/saved-strategy/enabled' &&
        method === 'PATCH'
      ) {
        const body = request.postDataJSON() as {
          enabled: boolean
          expected_version: number
        }
        if (rejectToggle) {
          rejectToggle = false
          await route.fulfill({
            status: 409,
            json: {
              code: 'PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT',
              message: '状态修改失败，请重新读取已保存策略',
            },
          })
          return
        }
        expect(body.expected_version).toBe(strategy!.version)
        strategy = {
          ...strategy!,
          enabled: body.enabled,
          version: body.expected_version + 1,
        }
        data = strategy
      } else if (path === '/api/v1/product-selection/runs' && method === 'GET')
        data = {
          items: run ? [run] : [],
          total: run ? 1 : 0,
          page: 1,
          page_size: 1,
        }
      else if (path === '/api/v1/product-selection/runs' && method === 'POST') {
        const body = request.postDataJSON()
        run = {
          run_id: 'submitted-run',
          request_shop_id: 'strategy-shop',
          status: 'pending',
          result_count: null,
          saved_count: 0,
          supplement_failed_count: 0,
          error_code: null,
        }
        strategy = {
          ...strategy!,
          latest_run: run as unknown as SelectionStrategyDto['latest_run'],
        }
        await route.fulfill({
          status: 202,
          json: {
            receipt_id: 'submitted-run',
            submission_key: body.submission_key,
            execution_run_id: 'submitted-run',
            reused: false,
            execution: run,
          },
        })
        return
      } else if (path === '/api/v1/product-selection/runs/submitted-run')
        data = run
      else {
        unexpected.push(`${method} ${path}`)
        await route.abort()
        return
      }
      await route.fulfill({ json: data })
    })
    await page.goto('/#/product-selection?tab=selection-strategy')
    await expect(page.getByText('暂无选品策略', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '新建策略', exact: true }).click()
    const drawer = page.locator('.n-drawer')
    const field = (label: string) =>
      drawer
        .locator('.n-form-item')
        .filter({
          has: page.locator('.n-form-item-label', {
            hasText: new RegExp(`^${label}$`),
          }),
        })
        .last()
    await field('请求店铺').locator('.n-base-selection').click()
    await page.getByText('授权合成店铺', { exact: true }).last().click()
    await field('类目').locator('.n-base-selection').click()
    await page.getByText(industryLabel, { exact: true }).last().click()
    await page.getByText(categoryLabel, { exact: true }).last().click()
    await page
      .locator('.n-cascader-submenu')
      .last()
      .getByText('全部', { exact: true })
      .click()
    if (period !== '7d')
      await field('日期')
        .getByText(
          { realtime: '实时', '1d': '近1天', '30d': '近30天' }[period],
          { exact: true },
        )
        .click()
    await drawer
      .getByRole('textbox', { name: '策略名称' })
      .fill('接口拦截合成策略')
    await field('首次上榜').getByRole('switch').click()
    await field('起始排名').locator('input').fill('151')
    await field('结束排名').locator('input').fill('200')
    await field('结束排名').locator('input').blur()
    await field('定时执行').getByRole('switch').click()
    await field('执行频率').locator('.n-base-selection').click()
    await page
      .locator('.n-base-select-menu')
      .getByText('每日', { exact: true })
      .click()
    await expect(field('每日时间').getByRole('textbox')).toHaveValue('09:00')
    for (const [preset, label] of [
      ['graphite', '石墨浅色'],
      ['forest', '森林绿'],
      ['coral', '珊瑚红'],
      ['midnight', '午夜青'],
    ]) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page
        .locator('.n-dropdown')
        .getByText(label!, { exact: true })
        .click()
      await settle(page)
      await page.screenshot({
        path: info.outputPath(`${preset}-intercepted-strategy-drawer.png`),
        animations: 'disabled',
      })
    }
    await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
    await expect(page.getByText('策略已保存', { exact: true })).toBeVisible()
    await expect(
      page.getByText('接口拦截合成策略', { exact: true }),
    ).toBeVisible()
    expect(writes).toHaveLength(1)
    expect(writes[0]!.path).toBe('/api/v1/product-selection/strategies')
    expect(JSON.stringify(writes[0]!.body)).not.toContain('begin_date')
    expect(strategy!.conditions.request.period).toBe(period)
    expect(strategy!.conditions.request.industry_id).toBe(industryId)
    expect(strategy!.conditions.request.category_ids).toEqual([categoryId])
    await page.reload()
    await expect(
      page.getByText('接口拦截合成策略', { exact: true }),
    ).toBeVisible()
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(field('类目').locator('.n-cascader')).toContainText(
      `${categoryLabel} / 全部`,
    )
    await expect(field('起始排名').locator('input')).toHaveValue('151')
    await expect(field('结束排名').locator('input')).toHaveValue('200')
    await expect(field('首次上榜').getByRole('switch')).toHaveAttribute(
      'aria-checked',
      'true',
    )
    await expect(field('每日时间').getByRole('textbox')).toHaveValue('09:00')
    // A second editor advances the stored version. A stale save must keep the
    // current drawer/draft and must not silently retry or submit a platform run.
    strategy = { ...strategy!, version: strategy!.version + 1 }
    await drawer
      .getByRole('textbox', { name: '策略名称' })
      .fill('接口拦截已保存编辑')
    await field('起始排名').locator('input').fill('152')
    await field('结束排名').locator('input').fill('199')
    await field('结束排名').locator('input').blur()
    await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
    await expect(
      page.getByText('策略已被修改，请刷新已保存内容；当前草稿未覆盖', {
        exact: true,
      }),
    ).toBeVisible()
    await expect(drawer).toBeVisible()
    await expect(drawer.getByRole('textbox', { name: '策略名称' })).toHaveValue(
      '接口拦截已保存编辑',
    )
    await expect(field('起始排名').locator('input')).toHaveValue('152')
    expect(strategy!.name).toBe('接口拦截合成策略')
    expect(strategy!.conditions.request.rank_from).toBe(151)
    expect(writes).toHaveLength(2)
    expect(writes[1]!.body.expected_version).toBe(1)
    expect(run).toBeNull()
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
    await page.reload()
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(field('起始排名').locator('input')).toHaveValue('151')
    await drawer
      .getByRole('textbox', { name: '策略名称' })
      .fill('接口拦截已保存编辑')
    await field('起始排名').locator('input').fill('152')
    await field('结束排名').locator('input').fill('199')
    await field('结束排名').locator('input').blur()
    await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
    await expect(
      page.getByText('接口拦截已保存编辑', { exact: true }),
    ).toBeVisible()
    expect(writes).toHaveLength(3)
    expect(writes[2]!.method).toBe('PUT')
    expect(writes[2]!.body.expected_version).toBe(2)
    expect(strategy!.version).toBe(3)
    expect(strategy!.conditions.request.rank_from).toBe(152)
    expect(strategy!.conditions.request.rank_to).toBe(199)
    expect(run).toBeNull()
    await page.reload()
    await expect(
      page.getByText('接口拦截已保存编辑', { exact: true }),
    ).toBeVisible()
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(field('起始排名').locator('input')).toHaveValue('152')
    await expect(field('结束排名').locator('input')).toHaveValue('199')
    await expect(field('每日时间').getByRole('textbox')).toHaveValue('09:00')
    await drawer
      .getByRole('textbox', { name: '策略名称' })
      .fill('不应被获取保存的改名')
    await field('起始排名').locator('input').fill('153')
    await field('结束排名').locator('input').fill('198')
    await field('结束排名').locator('input').blur()
    // The drawer switch edits a draft. Retrieval must not persist its state.
    await field('策略状态').getByRole('switch').click()
    await expect(field('策略状态').getByRole('switch')).toHaveAttribute(
      'aria-checked',
      'true',
    )
    await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
    await expect(page.getByText('等待获取', { exact: true })).toBeVisible()
    expect(strategy!.name).toBe('接口拦截已保存编辑')
    expect(strategy!.conditions.request.rank_from).toBe(152)
    expect(strategy!.enabled).toBe(false)
    expect(writes).toHaveLength(4)
    expect(writes[3]!.path).toBe('/api/v1/product-selection/runs')
    expect(writes[3]!.body).toMatchObject({
      strategy_id: 'saved-strategy',
      strategy_version: 3,
      period,
      industry_id: industryId,
      category_ids: [categoryId],
      first_listed_only: true,
      rank_from: 153,
      rank_to: 198,
    })
    await page
      .getByRole('switch', { name: '接口拦截已保存编辑启用状态' })
      .click()
    await expect(
      page.getByText('状态修改失败，请重新读取已保存策略', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('switch', { name: '接口拦截已保存编辑启用状态' }),
    ).toHaveAttribute('aria-checked', 'false')
    expect(strategy!.enabled).toBe(false)
    await page
      .getByRole('switch', { name: '接口拦截已保存编辑启用状态' })
      .click()
    await expect(
      page.getByRole('switch', { name: '接口拦截已保存编辑启用状态' }),
    ).toHaveAttribute('aria-checked', 'true')
    for (const [preset, label] of [
      ['graphite', '石墨浅色'],
      ['forest', '森林绿'],
      ['coral', '珊瑚红'],
      ['midnight', '午夜青'],
    ]) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page
        .locator('.n-dropdown')
        .getByText(label!, { exact: true })
        .click()
      await settle(page)
      await page
        .locator('.n-data-table-base-table-body .n-scrollbar-container')
        .first()
        .evaluate((element) => {
          element.scrollLeft = 0
        })
      await page.screenshot({
        path: info.outputPath(`${preset}-intercepted-strategy-list.png`),
        animations: 'disabled',
      })
    }
    expect(mocks).toEqual([])
    expect(unexpected).toEqual([])
  })
}
