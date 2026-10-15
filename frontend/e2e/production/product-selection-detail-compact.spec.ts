import { expect, test } from '@playwright/test'
import { readFile, writeFile } from 'node:fs/promises'
import type { SelectionObservationDto } from '../../src/features/product-selection/api/selection-read-api'
import { settleSelectionTransitions } from '../support/settle-selection-transitions'

// Real Renderer with every API/image intercepted. No database or platform calls.
for (const theme of ['graphite', 'forest', 'coral', 'midnight']) {
  test(`${theme}: detail scoped compact typography and paused footer`, async ({
    page,
  }, info) => {
    test.setTimeout(60000)
    await page.addInitScript((preset) => {
      localStorage.setItem('control-center.theme-mode', preset)
    }, theme)
    const at = '2026-10-15T02:00:00Z'
    const field = {
      last_attempt_state: 'available' as const,
      last_success_at: at,
    }
    const metric = {
      state: 'available' as const,
      retrieved_at: at,
      value_range: [
        { value: '0', value_type: 'int' as const, unit: 'number' },
        { value: '0', value_type: 'int' as const, unit: 'number' },
      ] as [
        { value: string; value_type: 'int'; unit: string },
        { value: string; value_type: 'int'; unit: string },
      ],
    }
    const row: SelectionObservationDto = {
      observation_id: 'detail-observation',
      candidate_id: 'detail-candidate',
      product_id: '9000000000000000001',
      last_run_id: 'rank-history',
      platform: 'douyin',
      request_shop_id: 'detail-shop',
      request_shop_name: '合成授权请求店铺',
      source_scope_hash: 'a'.repeat(64),
      source_context: {
        version: 1,
        platform: 'douyin',
        endpoint: 'product_rank/video_bring_good',
        business: {
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
        },
        date_selection: {
          policy: 'shanghai_7d_once',
          accepted_local_date: '2026-10-15',
          primary_begin: '2026-10-08',
          primary_end: '2026-10-14',
          backup_begin: '2026-10-07',
          backup_end: '2026-10-13',
          actual_window: 'primary',
          rank_from: 150,
          rank_to: 200,
        },
      },
      period_begin: '2026-10-08',
      period_end: '2026-10-14',
      title:
        '合成展示长标题：多规格带滤网收纳罐，完整商品信息与原始区间保留，前端拦截样本不是平台取数',
      image_url: '/detail-compact-product.webp',
      source_url: null,
      merchants: [
        { platform_shop_id: 'detail-merchant', name: '独立商品商家' },
      ],
      category_path: ['餐饮厨具', '厨房小工具', '收纳罐'],
      price_band: '10–50',
      rank: 150,
      previous_rank: 152,
      previous_checked_at: at,
      newly_on_ranking: false,
      first_seen_at: at,
      checked_at: '2026-10-15T01:50:00Z',
      metrics_retrieved_at: at,
      video_metric_ranges: {
        pay_amt: {
          ...metric,
          value_range: [
            { value: '1000000', value_type: 'int', unit: 'price' },
            { value: '5000000', value_type: 'int', unit: 'price' },
          ],
        },
        product_click_cnt: metric,
        pay_combo_cnt: {
          state: 'missing',
          retrieved_at: at,
          value_range: null,
        },
        video_cnt: {
          ...metric,
          value_range: [
            { value: '10', value_type: 'int', unit: 'number' },
            { value: '50', value_type: 'int', unit: 'number' },
          ],
        },
      },
      first_on_shelf_date: '2026-09-01',
      bad_comment_rate_raw: '0',
      bad_comment_rate_unit: 4,
      basic_info_retrieved_at: at,
      last_attempt_at: at,
      last_error_code: null,
      last_error_stage: null,
      blocked: false,
      discovery_state: 'known',
      basic_info_status: {
        version: 1,
        attempted_at: at,
        request_started_at: at,
        state: 'succeeded',
        category_path: field,
        first_on_shelf_date: field,
        bad_comment_rate: field,
        error_code: null,
        error_stage: null,
        platform_business_code: null,
      },
    }
    const unexpected: string[] = [],
      pageErrors: string[] = [],
      mockModules: string[] = []
    let writes = 0,
      external = 0
    page.on('pageerror', (error) => pageErrors.push(error.message))
    page.on('request', (request) => {
      if (request.url().includes('selection-mock-handlers'))
        mockModules.push(request.url())
    })
    await page.route('**/*', async (route) => {
      const request = route.request(),
        url = new URL(request.url()),
        path = url.pathname
      if (url.hostname !== '127.0.0.1') {
        external++
        await route.abort()
        return
      }
      if (path === '/detail-compact-product.webp') {
        await route.fulfill({
          contentType: 'image/webp',
          body: await readFile(
            new URL(
              '../../src/features/product-selection/fixtures/photos/product-1.webp',
              import.meta.url,
            ),
          ),
        })
        return
      }
      if (!path.startsWith('/api/')) {
        await route.continue()
        return
      }
      if (request.method() !== 'GET') writes++
      let data: unknown
      if (path === '/api/v1/auth/me')
        data = { user_id: 'detail-user', display_name: '详情拦截验证' }
      else if (path === '/api/v1/access/me/teams')
        data = [
          {
            membership_id: 'detail-member',
            team_id: 'detail-team',
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
              shop_id: row.request_shop_id,
              display_name: row.request_shop_name,
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
          execution_enabled: false,
          manual_execution_available: false,
          basic_info_available: false,
          strategy_save_available: true,
          schedule_execution_enabled: false,
          unavailable_reason: 'EXECUTION_DISABLED',
        }
      else if (
        path === '/api/v1/product-selection/strategies' ||
        path === '/api/v1/product-selection/runs'
      )
        data = { items: [], total: 0, page: 1, page_size: 100 }
      else if (path === '/api/v1/product-selection/candidates')
        data = {
          items: [row],
          total: 1,
          page: 1,
          page_size: 20,
          context: {
            receipt_id: null,
            execution_run_id: null,
            detail_state: null,
            execution: null,
            unknown_discovery_count: 0,
          },
        }
      else if (
        path === '/api/v1/product-selection/observations/detail-observation'
      )
        data = row
      else if (
        path ===
        '/api/v1/product-selection/observations/detail-observation/basic-info-run'
      )
        data = {
          run_id: 'historical-basic',
          operation_kind: 'basic_info',
          target_observation_id: row.observation_id,
          status: 'succeeded',
          saved_count: 0,
          supplemented_count: 1,
          supplement_failed_count: 0,
          error_code: null,
          error_stage: null,
          platform_business_code: null,
          created_at: at,
          finished_at: at,
        }
      else {
        unexpected.push(`${request.method()} ${path}`)
        await route.fulfill({
          status: 404,
          json: { code: 'TEST_UNEXPECTED', message: '未登记测试接口' },
        })
        return
      }
      await route.fulfill({ json: data })
    })
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
    const detail = page.locator('.n-drawer')
    for (const viewport of [
      { width: 1366, height: 768 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport)
      await page.goto('/#/product-selection')
      await page.getByRole('button', { name: '详情', exact: true }).click()
      await expect(
        detail.getByText('上次基础信息已更新', { exact: true }),
      ).toBeVisible()
      await expect(
        detail.getByText('当前环境暂停更新', { exact: true }),
      ).toBeVisible()
      for (const label of ['更新基础信息', '采集资料'])
        await expect(
          detail.getByRole('button', { name: label, exact: true }),
        ).toBeDisabled()
      await expect
        .poll(() =>
          detail
            .locator('.n-image img')
            .evaluate((image) => (image as HTMLImageElement).naturalWidth),
        )
        .toBeGreaterThan(0)
      await settleSelectionTransitions(page)
      const dimensions = await detail.evaluate((element) => {
        const style = (selector: string) => {
          const css = getComputedStyle(element.querySelector(selector)!)
          return {
            size: css.fontSize,
            weight: css.fontWeight,
            color: css.color,
          }
        }
        const rect = (selector: string) => {
          const bounds = element
            .querySelector(selector)!
            .getBoundingClientRect()
          return {
            x: bounds.x,
            y: bounds.y,
            right: bounds.right,
            bottom: bounds.bottom,
          }
        }
        return {
          title: style('.candidate-detail__title'),
          heading: style('.candidate-detail h3'),
          metric: style('.candidate-detail__metric'),
          missingMetricColor: getComputedStyle(
            element.querySelectorAll('.candidate-detail__metric')[2]!,
          ).color,
          label: style('.n-descriptions-table-header'),
          value: style('.n-descriptions-table-content'),
          metadata: style('.candidate-detail__metadata'),
          feedback: style('.candidate-detail__feedback'),
          buttons: [
            ...element.querySelectorAll('.candidate-detail__actions button'),
          ].map((button) => ({
            height: button.getBoundingClientRect().height,
            font: getComputedStyle(button).fontSize,
          })),
          statusRect: rect('.candidate-detail__feedback'),
          actionsRect: rect('.candidate-detail__actions'),
          overflow: [
            ...element.querySelectorAll(
              '.n-drawer-body-content-wrapper, .candidate-detail__summary, .candidate-detail__headline, .candidate-detail__footer',
            ),
          ].map((item) => item.scrollWidth - item.clientWidth),
        }
      })
      expect(dimensions.title).toMatchObject({ size: '16px', weight: '600' })
      expect(dimensions.heading).toMatchObject({ size: '14px', weight: '600' })
      expect(dimensions.metric).toMatchObject({ size: '18px', weight: '600' })
      expect(dimensions.label).toMatchObject({ size: '13px', weight: '400' })
      expect(dimensions.value).toMatchObject({ size: '13px', weight: '400' })
      expect(dimensions.metadata.size).toBe('12px')
      expect(dimensions.feedback.size).toBe('12px')
      expect(dimensions.value.color).toBe(dimensions.title.color)
      expect(dimensions.metric.color).toBe(dimensions.title.color)
      expect(dimensions.label.color).not.toBe(dimensions.value.color)
      expect(dimensions.metadata.color).not.toBe(dimensions.value.color)
      expect(dimensions.missingMetricColor).toBe(dimensions.metadata.color)
      expect(dimensions.buttons).toEqual(
        Array(3).fill({ height: 28, font: '13px' }),
      )
      expect(dimensions.overflow.every((value) => value <= 1)).toBe(true)
      const sameLine = dimensions.actionsRect.y < dimensions.statusRect.bottom
      expect(
        sameLine
          ? dimensions.actionsRect.x - dimensions.statusRect.right >= 11
          : dimensions.actionsRect.y - dimensions.statusRect.bottom >= 11,
      ).toBe(true)
      await expect(detail.locator('.candidate-detail__metric')).toHaveText([
        '¥1万–5万',
        '0–0',
        '—',
        '10–50',
      ])
      await expect(
        detail.locator('.candidate-detail__metadata').first(),
      ).toContainText('更新 10-15 10:00')
      await page.screenshot({
        path: info.outputPath(`${theme}-${viewport.width}-detail.png`),
        animations: 'disabled',
      })
      await writeFile(
        info.outputPath(`${theme}-${viewport.width}-detail.json`),
        JSON.stringify(
          {
            evidence:
              'Real Renderer / intercepted HTTP; not Electron or platform',
            viewport,
            dimensions,
          },
          null,
          2,
        ),
      )
      await detail.locator('.candidate-detail__metric').first().click()
      await detail.getByRole('button', { name: /^复制商品ID / }).click()
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
        row.product_id,
      )
      await detail.locator('.n-image img').click()
      await expect(page.locator('.n-image-preview-container')).toBeVisible()
      await page
        .locator('.n-image-preview-overlay')
        .click({ position: { x: 10, y: 10 } })
      await expect(page.locator('.n-image-preview-container')).toBeHidden()
      await detail.locator('.n-collapse-item__header-main').click()
      await expect(
        detail.getByText('榜单检查时间', { exact: true }),
      ).toBeVisible()
      await expect(
        detail.getByText('2026-10-15 09:50', { exact: true }),
      ).toBeVisible()
      await expect(
        detail.getByText('合成授权请求店铺', { exact: true }),
      ).toBeVisible()
      await expect(page.getByText('商品ID已复制', { exact: true })).toBeHidden()
      await detail.getByRole('button', { name: '关闭', exact: true }).click()
    }
    // Existing small Drawer token is a test-only constrained width, not a live layout change.
    await page.evaluate(() =>
      document.documentElement.style.setProperty(
        '--drawer-width-md',
        'var(--drawer-width-sm)',
      ),
    )
    await page.getByRole('button', { name: '详情', exact: true }).click()
    await expect(
      detail.getByText('当前环境暂停更新', { exact: true }),
    ).toBeVisible()
    await settleSelectionTransitions(page)
    const narrow = await detail.evaluate((element) => {
      const feedback = element
        .querySelector('.candidate-detail__feedback')!
        .getBoundingClientRect()
      const actions = element
        .querySelector('.candidate-detail__actions')!
        .getBoundingClientRect()
      const footer = element.querySelector('.candidate-detail__footer')!
      return {
        width: element.getBoundingClientRect().width,
        gap: actions.y - feedback.bottom,
        overflow: footer.scrollWidth - footer.clientWidth,
      }
    })
    expect(narrow.width).toBe(420)
    expect(narrow.gap).toBeGreaterThanOrEqual(11)
    expect(narrow.overflow).toBeLessThanOrEqual(1)
    await detail.locator('.candidate-detail__action-trigger').hover()
    await expect(page.locator('.n-tooltip:visible')).toContainText(
      '资料采集待接入',
    )
    await page.mouse.move(10, 10)
    await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)
    await settleSelectionTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${theme}-detail-narrow420.png`),
      animations: 'disabled',
    })
    expect({ writes, external, unexpected, pageErrors, mockModules }).toEqual({
      writes: 0,
      external: 0,
      unexpected: [],
      pageErrors: [],
      mockModules: [],
    })
  })
}
