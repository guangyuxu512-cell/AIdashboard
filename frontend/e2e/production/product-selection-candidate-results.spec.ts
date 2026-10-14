import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { settleSelectionTransitions } from '../support/settle-selection-transitions'

// Real Renderer, completely intercepted HTTP. Not DB, platform or Electron proof.
for (const theme of ['graphite', 'forest', 'coral', 'midnight']) {
  test(`${theme}: scoped results, blocking and single-basic progress preserve rank values`, async ({
    page,
  }, info) => {
    test.setTimeout(90000)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.addInitScript(
      (preset) => localStorage.setItem('control-center.theme-mode', preset),
      theme,
    )
    const at = '2026-10-15T02:00:00Z'
    const scope = {
      industry_id: '7',
      category_id: '1001,1002',
      brand_type: '-1',
      price_bin: '不限',
      search_info: '',
      rank_data_type: '1',
      begin_date: '2026/10/08 00:00:00',
      end_date: '2026/10/14 00:00:00',
      date_type: '21',
      activity_id: '',
    }
    const run = {
      run_id: 'rank-1',
      request_shop_id: 'shop-1',
      status: 'partial',
      result_count: 1,
      saved_count: 1,
      supplement_failed_count: 1,
      error_code: 'PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE',
      error_stage: 'basic_info',
      request_conditions: { version: 8, scope },
    }
    const metric = {
      state: 'available',
      retrieved_at: at,
      value_range: [
        { value: '0', value_type: 'int', unit: 'number' },
        { value: '0', value_type: 'int', unit: 'number' },
      ],
    }
    const row = {
      observation_id: 'observation-1',
      candidate_id: 'candidate-1',
      product_id: '9000000000000000001',
      last_run_id: 'rank-1',
      result_run_id: 'rank-1',
      platform: 'douyin',
      request_shop_id: 'shop-1',
      request_shop_name: '授权合成店铺',
      source_scope_hash: 'a'.repeat(64),
      source_context: {
        version: 1,
        platform: 'douyin',
        endpoint: 'product_rank/video_bring_good',
        business: scope,
        date_selection: {
          policy: 'shanghai_7d_once',
          accepted_local_date: '2026-10-15',
          primary_begin: '2026-10-08',
          primary_end: '2026-10-14',
          backup_begin: '2026-10-07',
          backup_end: '2026-10-13',
          actual_window: 'primary',
          fallback_reason: null,
          rank_from: 150,
          rank_to: 200,
        },
      },
      period_begin: '2026-10-08',
      period_end: '2026-10-14',
      title:
        '合成契约长标题：来源与视频指标保留，基础信息可单独更新，测试不是平台实测',
      image_url: '/synthetic-product.webp',
      source_url: null,
      merchants: [{ platform_shop_id: 'merchant-1', name: '独立商品商家' }],
      category_path: ['行业', '末级类目'],
      price_band: '10–50',
      rank: 198,
      previous_rank: 200,
      previous_checked_at: at,
      newly_on_ranking: false,
      first_seen_at: at,
      checked_at: at,
      metrics_retrieved_at: at,
      video_metric_ranges: {
        pay_amt: metric,
        pay_combo_cnt: metric,
        product_click_cnt: {
          state: 'invalid',
          retrieved_at: at,
          value_range: null,
        },
        video_cnt: metric,
      },
      first_on_shelf_date: null,
      bad_comment_rate_raw: '0',
      bad_comment_rate_unit: 4,
      basic_info_retrieved_at: null,
      last_attempt_at: at,
      last_error_code: 'DOUYIN_SELECTION_BUSINESS_REJECTED',
      last_error_stage: 'basic_info_request',
      blocked: false,
      discovery_state: 'new',
      basic_info_status: null as Record<string, unknown> | null,
    }
    const strategy = {
      strategy_id: 'strategy-1',
      name: '真实契约策略示例',
      shop_id: 'shop-1',
      shop_name: '授权合成店铺',
      version: 1,
      enabled: true,
      conditions: {
        version: 1,
        request: {
          channel: 'short-video',
          period: '7d',
          industry_id: '7',
          category_ids: ['1001', '1002'],
          brand: 'all',
          price_mode: 'all',
          price_above: null,
          price_below: null,
          first_listed_only: false,
          rank_from: 150,
          rank_to: 200,
        },
      },
      schedule: {
        scheduled: false,
        kind: 'hourly',
        interval_hours: 3,
        daily_time: '09:00',
      },
      schedule_available: true,
      schedule_execution_enabled: false,
      next_run_at: null,
      latest_run: run,
      latest_receipt_id: 'receipt-1',
    }
    let basic: Record<string, unknown> | null = null
    let finishBasic = false
    let posts = 0,
      patches = 0,
      reads = 0
    const candidateQueries: URLSearchParams[] = [],
      unexpected: string[] = [],
      mocks: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('selection-mock-handlers'))
        mocks.push(request.url())
    })
    await page.route('**/synthetic-product.webp', async (route) =>
      route.fulfill({
        body: await readFile(
          new URL(
            '../../src/features/product-selection/fixtures/photos/product-1.webp',
            import.meta.url,
          ),
        ),
        contentType: 'image/webp',
      }),
    )
    await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
      const request = route.request(),
        url = new URL(request.url()),
        path = url.pathname,
        method = request.method()
      let data: unknown
      if (path === '/api/v1/auth/me')
        data = { user_id: 'test-person', display_name: 'API拦截验证' }
      else if (path === '/api/v1/access/me/teams')
        data = [
          {
            membership_id: 'test-member',
            team_id: 'test-team',
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
              shop_id: 'shop-1',
              display_name: '授权合成店铺',
              platform: 'douyin',
              enabled: true,
              owner_user_id: null,
              note: null,
              created_at: at,
              updated_at: at,
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
          strategy_save_available: true,
          schedule_available: true,
          schedule_execution_enabled: false,
          basic_info_available: true,
          candidate_block_available: true,
          unavailable_reason: null,
        }
      else if (path === '/api/v1/product-selection/strategies')
        data = { items: [strategy], total: 1, page: 1, page_size: 100 }
      else if (path === '/api/v1/product-selection/strategies/strategy-1')
        data = strategy
      else if (
        path === '/api/v1/product-selection/strategies/strategy-1/batches'
      )
        data = {
          items: [
            {
              receipt_id: 'receipt-1',
              execution_run_id: 'rank-1',
              submitted_at: at,
              detail_state: 'recorded',
              visible_item_count: 1,
              execution: run,
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        }
      else if (path === '/api/v1/product-selection/runs')
        data = { items: [run], total: 1, page: 1, page_size: 1 }
      else if (path === '/api/v1/product-selection/candidates') {
        candidateQueries.push(url.searchParams)
        const blocked = url.searchParams.get('blocked') === 'true'
        data = {
          items: blocked === row.blocked ? [row] : [],
          total: blocked === row.blocked ? 1 : 0,
          page: 1,
          page_size: 10,
          context: {
            receipt_id: url.searchParams.get('receipt_id'),
            execution_run_id: url.searchParams.get('receipt_id')
              ? 'rank-1'
              : null,
            detail_state: url.searchParams.get('receipt_id')
              ? 'recorded'
              : null,
            execution: null,
            unknown_discovery_count: 0,
          },
        }
      } else if (
        path === '/api/v1/product-selection/observations/observation-1'
      )
        data = row
      else if (path.endsWith('/observation-1/blocked') && method === 'PATCH') {
        patches++
        row.blocked = request.postDataJSON().blocked
        data = row
      } else if (path.endsWith('/observation-1/basic-info-run')) {
        reads++
        if (basic && finishBasic) {
          basic = {
            ...basic,
            status: 'succeeded',
            supplemented_count: 1,
            finished_at: '2026-10-15T02:05:00Z',
          }
          row.first_on_shelf_date = '2026-10-01'
          row.last_error_code = null
          row.last_error_stage = null
          row.basic_info_status = {
            version: 1,
            attempted_at: '2026-10-15T02:05:00Z',
            request_started_at: at,
            state: 'succeeded',
            error_code: null,
            error_stage: null,
            platform_business_code: null,
            category_path: {
              last_attempt_state: 'available',
              last_success_at: '2026-10-15T02:05:00Z',
            },
            first_on_shelf_date: {
              last_attempt_state: 'available',
              last_success_at: '2026-10-15T02:05:00Z',
            },
            bad_comment_rate: {
              last_attempt_state: 'available',
              last_success_at: '2026-10-15T02:05:00Z',
            },
          }
        }
        data = basic
      } else if (
        path === '/api/v1/product-selection/basic-info-runs' &&
        method === 'POST'
      ) {
        posts++
        expect(request.postDataJSON().observation_id).toBe('observation-1')
        expect(request.postDataJSON().submission_key).toMatch(/^[a-f0-9-]{36}$/)
        basic = {
          run_id: 'basic-1',
          operation_kind: 'basic_info',
          target_observation_id: 'observation-1',
          status: 'pending',
          saved_count: 0,
          supplemented_count: 0,
          supplement_failed_count: 0,
          error_code: null,
          error_stage: null,
          platform_business_code: null,
          created_at: at,
          finished_at: null,
        }
        data = {
          receipt_id: 'basic-receipt',
          submission_key: request.postDataJSON().submission_key,
          execution_run_id: 'basic-1',
          reused: false,
          execution: basic,
        }
      } else {
        unexpected.push(`${method} ${path}`)
        await route.fulfill({
          status: 404,
          json: { code: 'TEST_UNEXPECTED', message: '未登记测试接口' },
        })
        return
      }
      await route.fulfill({ status: method === 'POST' ? 202 : 200, json: data })
    })
    await page.goto('/#/product-selection')
    await expect(
      page.getByRole('button', { name: '详情', exact: true }),
    ).toBeVisible()
    await expect(page.getByText('演示数据', { exact: true })).toHaveCount(0)
    await page.getByLabel('结果范围').click()
    await page.getByText('今日新发现', { exact: true }).click()
    await expect
      .poll(() => candidateQueries.at(-1)?.get('result_scope'))
      .toBe('today_new')
    await page.reload()
    await expect(page.getByLabel('结果范围')).toContainText('今日新发现')
    await page.getByRole('button', { name: '详情', exact: true }).click()
    await expect(page.getByText('罗盘视频数据', { exact: true })).toBeVisible()
    await expect(
      page.getByRole('button', { name: '采集资料', exact: true }).last(),
    ).toBeDisabled()
    await page
      .getByRole('button', { name: '更新基础信息', exact: true })
      .click()
    await expect(
      page.getByRole('button', { name: /更新基础信息/ }),
    ).toBeDisabled()
    finishBasic = true
    await expect(
      page.getByText('基础信息已更新', { exact: true }).first(),
    ).toBeVisible({ timeout: 10000 })
    expect(posts).toBe(1)
    expect(reads).toBeGreaterThanOrEqual(3)
    await expect(
      page.getByRole('button', { name: '更新基础信息', exact: true }),
    ).toBeEnabled()
    expect(row.metrics_retrieved_at).toBe(at)
    expect(row.last_run_id).toBe('rank-1')
    await settleSelectionTransitions(page)
    await page.screenshot({
      path: info.outputPath(`detail-${theme}.png`),
      fullPage: true,
    })
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await page.getByRole('button', { name: '屏蔽', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '详情', exact: true }),
    ).toHaveCount(0)
    await page.getByLabel('屏蔽状态筛选').click()
    await page
      .locator('.n-base-select-option:visible')
      .filter({ hasText: /^已屏蔽$/ })
      .click()
    await page.getByRole('button', { name: '恢复', exact: true }).click()
    expect(patches).toBe(2)
    await page.getByLabel('屏蔽状态筛选').click()
    await page
      .locator('.n-base-select-option:visible')
      .filter({ hasText: /^未屏蔽$/ })
      .click()
    await page.getByLabel('选品策略筛选').click()
    await page.getByText('真实契约策略示例', { exact: true }).click()
    await expect
      .poll(() => candidateQueries.at(-1)?.get('receipt_id'))
      .toBe('receipt-1')
    await page.reload()
    await expect(page.getByLabel('执行批次')).toContainText('最近执行')
    await page.getByLabel('执行批次').click()
    await expect(
      page
        .locator('.n-base-select-option:visible')
        .filter({ hasText: '可见 1 项' }),
    ).toBeVisible()
    await page.keyboard.press('Escape')
    await page.goBack()
    await expect(page.getByLabel('选品策略筛选')).toContainText('全部策略')
    await page.goForward()
    await expect(page.getByLabel('选品策略筛选')).toContainText(
      '真实契约策略示例',
    )
    await page.goBack()
    await page.getByRole('button', { name: '刷新列表', exact: true }).click()
    expect(posts).toBe(1)
    await page.locator('.n-image img').first().waitFor()
    await expect
      .poll(() =>
        page
          .locator('.n-image img')
          .first()
          .evaluate((image) => (image as HTMLImageElement).naturalWidth),
      )
      .toBeGreaterThan(0)
    await settleSelectionTransitions(page)
    await page.screenshot({
      path: info.outputPath(`list-${theme}.png`),
      fullPage: true,
    })
    await page.setViewportSize({ width: 1366, height: 768 })
    await expect(
      page.getByRole('button', { name: '详情', exact: true }),
    ).toBeInViewport()
    await expect(
      page.getByRole('button', { name: '屏蔽', exact: true }),
    ).toBeInViewport()
    expect(unexpected).toEqual([])
    expect(mocks).toEqual([])
  })
}
