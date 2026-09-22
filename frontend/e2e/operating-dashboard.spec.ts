import { expect, test, type Page } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

async function getMixedPlatformAlignment(
  page: Page,
  tableSelector: string,
) {
  return page.evaluate((selector) => {
    const displays = Array.from(
      document.querySelectorAll(`${selector} .platform-display`),
    ).map((display) => {
      const iconSlot = display.querySelector('.platform-display__icon-slot')
      const label = display.querySelector('.platform-display__label')
      if (!iconSlot || !label) return null
      const displayRect = display.getBoundingClientRect()
      const iconRect = iconSlot.getBoundingClientRect()
      const labelRect = label.getBoundingClientRect()
      return {
        label: label.textContent,
        width: displayRect.width,
        iconLeft: iconRect.left,
        labelLeft: labelRect.left,
        verticallyAligned:
          Math.abs(
            iconRect.top + iconRect.height / 2 -
              (labelRect.top + labelRect.height / 2),
          ) <= 1,
      }
    })
    const douyin = displays.find((display) => display?.label === '抖店')
    const pdd = displays.find((display) => display?.label === '拼多多')
    return douyin && pdd
      ? {
          fixedWidth: Math.abs(douyin.width - pdd.width) <= 1,
          iconStart: Math.abs(douyin.iconLeft - pdd.iconLeft) <= 1,
          labelStart: Math.abs(douyin.labelLeft - pdd.labelLeft) <= 1,
          verticallyAligned: douyin.verticallyAligned && pdd.verticallyAligned,
        }
      : null
  }, tableSelector)
}

test('uses the UI-only dashboard fixture for filtering, stable experience columns and refresh feedback', async ({
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
  ).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: '抖店' }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('row').filter({ hasText: '示例店铺 A' }),
  ).toContainText('—')

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
  await page.getByText('抖店', { exact: true }).last().click()
  await expect(
    page.getByRole('columnheader', { name: '商家体验分' }),
  ).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: 'HuanYu' }),
  ).toContainText('81分')

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
    return {
      rowHeight: Math.round(row?.getBoundingClientRect().height ?? 0),
      headerHeight: Math.round(header?.getBoundingClientRect().height ?? 0),
    }
  })
  const shopPlatformAlignment = await getMixedPlatformAlignment(
    page,
    '.shop-list-table',
  )

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
    const alignments = Array.from(
      document.querySelectorAll(
        '.operating-dashboard-table .n-data-table-tbody .n-data-table-tr:first-child .n-data-table-td',
      ),
    ).map((cell) => getComputedStyle(cell).textAlign)
    return {
      rowHeight: Math.round(row?.getBoundingClientRect().height ?? 0),
      headerHeight: Math.round(header?.getBoundingClientRect().height ?? 0),
      alignments,
    }
  })
  const dashboardPlatformAlignment = await getMixedPlatformAlignment(
    page,
    '.operating-dashboard-table',
  )

  expect(dashboardTableMetrics.rowHeight).toBe(shopTableMetrics.rowHeight)
  expect(dashboardTableMetrics.headerHeight).toBe(shopTableMetrics.headerHeight)
  expect(dashboardTableMetrics.alignments.slice(2, 6)).toEqual([
    'center',
    'center',
    'center',
    'center',
  ])
  expect(shopPlatformAlignment).toEqual({
    fixedWidth: true,
    iconStart: true,
    labelStart: true,
    verticallyAligned: true,
  })
  expect(dashboardPlatformAlignment).toEqual({
    fixedWidth: true,
    iconStart: true,
    labelStart: true,
    verticallyAligned: true,
  })
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

test('sorts the complete Mock result before pagination and preserves the active sorter', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/operating-dashboard')

  const table = page.locator('.operating-dashboard-table')
  const pagination = page.locator('.pagination-bar')
  const header = (name: string) =>
    table.getByRole('columnheader', { name, exact: true })
  const sorter = (name: string) => header(name).locator('.n-data-table-sorter')

  await expect(
    table.locator('.n-data-table-tbody .n-data-table-tr').first(),
  ).toBeVisible()

  await pagination.getByText('2', { exact: true }).click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('2')

  await sorter('成交金额').click()
  await expect(sorter('成交金额')).toHaveClass(/n-data-table-sorter--desc/)
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(
    table.locator('.n-data-table-tbody .n-data-table-tr').first(),
  ).toContainText('HuanYu')

  await sorter('成交金额').click()
  await expect(sorter('成交金额')).toHaveClass(/n-data-table-sorter--asc/)
  await expect(
    table.locator('.n-data-table-tbody .n-data-table-tr').first(),
  ).toContainText('示例店铺 H')

  await sorter('成交金额').click()
  await expect(sorter('成交金额')).not.toHaveClass(/n-data-table-sorter--(?:asc|desc)/)
  await expect(
    table.locator('.n-data-table-tbody .n-data-table-tr').first(),
  ).toContainText('示例店铺 A')

  for (const [name, firstDirection] of [
    ['店铺', 'asc'],
    ['成交订单', 'desc'],
    ['退货数量', 'desc'],
    ['更新时间', 'desc'],
  ]) {
    await sorter(name).click()
    await expect(sorter(name)).toHaveClass(
      new RegExp(`n-data-table-sorter--${firstDirection}`),
    )
    await sorter(name).click()
    await sorter(name).click()
    await expect(sorter(name)).not.toHaveClass(
      /n-data-table-sorter--(?:asc|desc)/,
    )
  }

  await sorter('成交金额').click()
  const filter = page.getByRole('region', { name: '筛选条件' })
  await filter.locator('.n-base-selection').last().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .last()
    .getByText('拼多多', { exact: true })
    .click()
  await expect(sorter('成交金额')).toHaveClass(/n-data-table-sorter--desc/)
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')

  await page.getByRole('button', { name: '更新数据', exact: true }).click()
  await sorter('成交金额').click()
  await expect(sorter('成交金额')).toHaveClass(/n-data-table-sorter--asc/)
  await expect(page.getByRole('status')).toContainText('已完成')
  await expect(sorter('成交金额')).toHaveClass(/n-data-table-sorter--asc/)
})
