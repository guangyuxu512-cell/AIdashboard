import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('uses the UI-only dashboard fixture for filtering, pagination and refresh feedback', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/operating-dashboard')

  await expect(page).toHaveURL(/#\/operating-dashboard$/)
  await expect(page.getByRole('region', { name: '经营概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /成交趋势/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '店铺' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '商家体验分' })).toBeVisible()

  await page.getByText('近3天', { exact: true }).click()
  await expect(page.getByText('较上期', { exact: true })).toHaveCount(4)
  await expect(
    page.getByRole('heading', { name: /至 .*成交趋势/ }),
  ).toBeVisible()

  const filter = page.getByRole('region', { name: '筛选条件' })
  await filter.locator('.n-base-selection').last().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .last()
    .getByText('拼多多', { exact: true })
    .click()
  await expect(
    page.getByRole('columnheader', { name: '商家体验分' }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('row').filter({ hasText: '抖店' }),
  ).toHaveCount(0)

  await filter.locator('.n-base-selection').first().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .last()
    .getByText('示例店铺 A', { exact: true })
    .click()
  await expect(
    page.getByRole('row').filter({ hasText: '示例店铺 A' }),
  ).toHaveCount(1)

  await filter.locator('.n-base-selection').first().click()
  await page.getByText('全部店铺', { exact: true }).last().click()
  await expect(
    page.getByRole('row').filter({ hasText: '示例店铺 B' }),
  ).toHaveCount(1)

  await filter.locator('.n-base-selection').last().click()
  await page.getByText('全部平台', { exact: true }).last().click()
  await expect(
    page.getByRole('columnheader', { name: '商家体验分' }),
  ).toBeVisible()

  await page.reload()
  const pagination = page.locator('.pagination-bar')
  await pagination.getByText('2', { exact: true }).click()
  await expect(
    page.getByRole('row').filter({ hasText: 'MyCookLab' }),
  ).toBeVisible()

  await page.getByRole('button', { name: '更新数据', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已更新 10 家')
  await page.getByRole('button', { name: '更新数据', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已完成 11 家店铺')
  expect(runtimeErrors).toEqual([])
})

test('keeps the filter chrome mounted and gives the custom date range enough width', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/operating-dashboard')
  await expect(page.getByRole('region', { name: '经营概览' })).toBeVisible()

  await page.getByText('自定义', { exact: true }).click()
  const dateRange = page.locator('.app-date-picker--range')
  const startInput = page.getByPlaceholder('开始日期')
  const endInput = page.getByPlaceholder('结束日期')
  await expect(dateRange).toBeVisible()
  await expect(startInput).toBeVisible()
  await expect(endInput).toBeVisible()

  const dateLayout = await page.evaluate(() => {
    const range = document.querySelector('.app-date-picker--range')
    const start = document.querySelector<HTMLInputElement>(
      'input[placeholder="开始日期"]',
    )
    const end = document.querySelector<HTMLInputElement>(
      'input[placeholder="结束日期"]',
    )
    if (!range || !start || !end) return null

    const rangeRect = range.getBoundingClientRect()
    const startRect = start.getBoundingClientRect()
    const endRect = end.getBoundingClientRect()
    return {
      rangeWidth: Math.round(rangeRect.width),
      rangeRight: Math.round(rangeRect.right),
      viewportWidth: window.innerWidth,
      startWithinRange: startRect.left >= rangeRect.left && startRect.right <= rangeRect.right,
      endWithinRange: endRect.left >= rangeRect.left && endRect.right <= rangeRect.right,
    }
  })
  expect(dateLayout).toEqual({
    rangeWidth: 264,
    rangeRight: expect.any(Number),
    viewportWidth: 1440,
    startWithinRange: true,
    endWithinRange: true,
  })
  expect(dateLayout!.rangeRight).toBeLessThanOrEqual(dateLayout!.viewportWidth)

  await page.getByText('近3天', { exact: true }).click()
  await expect(page.getByRole('region', { name: '经营概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /成交趋势/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '店铺' })).toBeVisible()
  await expect(page.getByText('正在加载经营数据…')).toHaveCount(0)
  await expect(page.getByText('较上期', { exact: true })).toHaveCount(4)
})

test('matches the shop list table density and centers dashboard metric cells', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/shops')
  await expect(page.locator('.n-data-table-tbody .n-data-table-tr').first()).toBeVisible()
  const shopTableMetrics = await page.evaluate(() => {
    const row = document.querySelector('.n-data-table-tbody .n-data-table-tr')
    const header = document.querySelector('.n-data-table-thead .n-data-table-th')
    const platformDisplay = document.querySelector('.platform-display')
    const iconSlot = document.querySelector('.platform-display__icon-slot')
    const label = document.querySelector('.platform-display__label')
    const platformAligned =
      platformDisplay && iconSlot && label
        ? Math.abs(
            iconSlot.getBoundingClientRect().top +
              iconSlot.getBoundingClientRect().height / 2 -
              (label.getBoundingClientRect().top +
                label.getBoundingClientRect().height / 2),
          ) <= 1
        : false
    return {
      rowHeight: Math.round(row?.getBoundingClientRect().height ?? 0),
      headerHeight: Math.round(header?.getBoundingClientRect().height ?? 0),
      platformAligned,
    }
  })

  await page.goto('/#/operating-dashboard')
  await expect(
    page.locator('.operating-dashboard-table .n-data-table-tbody .n-data-table-tr').first(),
  ).toBeVisible()
  const dashboardTableMetrics = await page.evaluate(() => {
    const row = document.querySelector(
      '.operating-dashboard-table .n-data-table-tbody .n-data-table-tr',
    )
    const header = document.querySelector(
      '.operating-dashboard-table .n-data-table-thead .n-data-table-th',
    )
    const platformDisplay = document.querySelector(
      '.operating-dashboard-table .platform-display',
    )
    const iconSlot = document.querySelector(
      '.operating-dashboard-table .platform-display__icon-slot',
    )
    const label = document.querySelector(
      '.operating-dashboard-table .platform-display__label',
    )
    const alignments = Array.from(
      document.querySelectorAll(
        '.operating-dashboard-table .n-data-table-tbody .n-data-table-tr:first-child .n-data-table-td',
      ),
    ).map((cell) => getComputedStyle(cell).textAlign)
    const platformAligned =
      platformDisplay && iconSlot && label
        ? Math.abs(
            iconSlot.getBoundingClientRect().top +
              iconSlot.getBoundingClientRect().height / 2 -
              (label.getBoundingClientRect().top +
                label.getBoundingClientRect().height / 2),
          ) <= 1
        : false
    return {
      rowHeight: Math.round(row?.getBoundingClientRect().height ?? 0),
      headerHeight: Math.round(header?.getBoundingClientRect().height ?? 0),
      alignments,
      platformAligned,
    }
  })

  expect(dashboardTableMetrics.rowHeight).toBe(shopTableMetrics.rowHeight)
  expect(dashboardTableMetrics.headerHeight).toBe(shopTableMetrics.headerHeight)
  expect(dashboardTableMetrics.alignments.slice(2, 6)).toEqual([
    'center',
    'center',
    'center',
    'center',
  ])
  expect(shopTableMetrics.platformAligned).toBe(true)
  expect(dashboardTableMetrics.platformAligned).toBe(true)
})

test('keeps the dashboard table and pagination inside the desktop renderer', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/#/operating-dashboard')
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
  await expect(page.locator('.pagination-bar')).toBeVisible()

  for (const theme of ['浅色', '深色']) {
    await page.getByRole('button', { name: '切换主题', exact: true }).click()
    await page.getByText(theme, { exact: true }).click()
    const layout = await page.evaluate(() => ({
      document:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      body: document.body.scrollWidth > document.body.clientWidth,
      tableHasScrollableViewport:
        document.querySelector('.operating-dashboard-table') !== null,
    }))
    expect(layout).toEqual({
      document: false,
      body: false,
      tableHasScrollableViewport: true,
    })
  }
})
