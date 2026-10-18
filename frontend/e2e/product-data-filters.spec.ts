import { expect, test, type Page } from '@playwright/test'

const rowSelector = '.product-data-table .n-data-table-tbody .n-data-table-tr'
const rangeIds = [
  'exposureCount',
  'clickCount',
  'exposureClickRate',
  'cartUsers',
  'visitCartRate',
  'netOrders',
  'refundRelatedOrders',
  'clickPayRate',
  'payTimeRefundRate',
]
async function open(page: Page) {
  await page.goto('/#/product-data')
  await expect(page.locator(rowSelector)).toHaveCount(20)
  await page.getByRole('button', { name: '更多筛选', exact: true }).click()
  await expect(page.locator('[data-metric-filter]')).toHaveCount(9)
}
async function choose(page: Page, selector: string, text: string) {
  await page.locator(selector).click()
  await page
    .locator('.app-select-menu--viewport-safe:visible')
    .getByText(text, { exact: true })
    .click()
  await expect(
    page.locator('.app-select-menu--viewport-safe:visible'),
  ).toHaveCount(0)
}

test('nine range presets, custom validation and full-set filtering keep the last page and hidden columns honest', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await open(page)
  await expect(page.locator('.product-range-field__bounds input')).toHaveCount(
    0,
  )
  for (const id of rangeIds) {
    await page
      .locator('[data-metric-filter="' + id + '"] .n-base-selection')
      .click()
    const menu = page.locator('.app-select-menu--viewport-safe:visible')
    await expect(menu.locator('.n-base-select-option')).toHaveCount(7)
    await expect(menu.getByText('不限', { exact: true })).toBeVisible()
    await expect(menu.getByText('自定义', { exact: true })).toBeVisible()
    if (id === 'clickPayRate')
      await expect(menu.getByText('4%–<6%', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(menu).toHaveCount(0)
  }
  await page.locator('.pagination-bar').getByText('2', { exact: true }).click()
  await choose(
    page,
    '[data-metric-filter="exposureCount"] .n-base-selection',
    '自定义',
  )
  const min = page.getByRole('textbox', { name: '曝光下限', exact: true }),
    max = page.getByRole('textbox', { name: '曝光上限', exact: true })
  await expect(min).toBeVisible()
  await min.fill('-1')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: '不能输入负数' }),
  ).toBeVisible()
  await expect(page.locator('.n-pagination-item--active')).toHaveText('2')
  await min.fill('10')
  await max.fill('5')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(
    page.getByRole('alert').filter({ hasText: '上限必须大于下限' }),
  ).toBeVisible()
  await min.fill('0')
  await max.fill('1000')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.locator('.pagination-bar')).toContainText('共 8 条')
  await expect(page.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(
    page.locator(rowSelector).filter({ hasText: '演示商品 28' }),
  ).toHaveCount(1)
  await page.getByRole('button', { name: '字段配置', exact: true }).click()
  const dialog = page.locator('.app-dialog')
  await expect(
    dialog.getByRole('checkbox', { name: '点击率', exact: true }),
  ).toHaveCount(1)
  await expect(
    dialog.getByRole('checkbox', { name: '曝光点击率', exact: true }),
  ).toHaveCount(1)
  await expect(
    dialog.getByRole('checkbox', { name: '曝光点击率', exact: true }),
  ).not.toBeChecked()
  await dialog.getByRole('checkbox', { name: '曝光人数', exact: true }).click()
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(min).toHaveValue('0')
  await expect(page.locator('.pagination-bar')).toContainText('共 8 条')
  await page.screenshot({
    path: info.outputPath('product-data-custom-filter.png'),
    animations: 'disabled',
  })
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.locator(rowSelector)).toHaveCount(20)
  await expect(page.locator('.product-range-field__bounds input')).toHaveCount(
    0,
  )
  expect(errors).toEqual([])
})

test('shows the total payment-time refund rate in fields, details and interval filtering', async ({
  page,
}, info) => {
  await open(page)
  await expect(page.locator('.product-data-filters__more')).not.toContainText(
    '退货率',
  )
  const field = page.locator('[data-metric-filter="payTimeRefundRate"]')
  await expect(field).toContainText('退款率')
  await choose(
    page,
    '[data-metric-filter="payTimeRefundRate"] .n-base-selection',
    '10%–<20%',
  )
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.locator('.pagination-bar')).toContainText('共 5 条')
  await page.getByRole('button', { name: '字段配置', exact: true }).click()
  const dialog = page.locator('.app-dialog')
  await expect(
    dialog.getByRole('checkbox', { name: '退货率', exact: true }),
  ).toHaveCount(0)
  await expect(
    dialog.getByRole('checkbox', { name: '退款率', exact: true }),
  ).toBeChecked()
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  const header = page
    .locator('.product-data-table')
    .getByRole('columnheader', { name: '退款率', exact: true })
  await expect(header).toBeAttached()
  await header.scrollIntoViewIfNeeded()
  await header.getByText('退款率', { exact: true }).hover()
  const tooltip = page
    .locator('.n-tooltip:visible')
    .filter({ hasText: '官方口径：退款率（支付时间）' })
  await expect(tooltip).toBeVisible()
  const tooltipBox = await tooltip.boundingBox()
  expect(tooltipBox!.x).toBeGreaterThanOrEqual(0)
  expect(tooltipBox!.x + tooltipBox!.width).toBeLessThanOrEqual(
    page.viewportSize()!.width,
  )
  await page.screenshot({
    path: info.outputPath('payment-time-refund-rate-tooltip.png'),
    animations: 'disabled',
  })
  await page.getByRole('button', { name: '详情', exact: true }).first().click()
  await expect(page.locator('.n-drawer')).toContainText('退款率')
  await expect(page.locator('.n-drawer')).not.toContainText('退货率')
  await page
    .locator('.n-drawer')
    .getByText('退款率', { exact: true })
    .scrollIntoViewIfNeeded()
  await page.screenshot({
    path: info.outputPath('payment-time-refund-rate.png'),
    animations: 'disabled',
  })
})

test('combines self/cooperation, all four carriers, shop and group without fetching platform data', async ({
  page,
}) => {
  await open(page)
  await choose(
    page,
    '.product-data-filters .n-base-selection >> nth=0',
    '星河服饰旗舰店',
  )
  await choose(
    page,
    '.product-data-filters .n-base-selection >> nth=1',
    '未分组',
  )
  await choose(page, '.product-data-filters .n-base-selection >> nth=2', '合作')
  await choose(page, '.product-data-filters .n-base-selection >> nth=3', '图文')
  await page
    .getByRole('textbox', { name: '商品名称', exact: true })
    .fill('演示商品 16')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.locator(rowSelector)).toHaveCount(1)
  await expect(page.locator('.pagination-bar')).toContainText('共 1 条')
  await expect(page.locator(rowSelector).first()).toContainText('演示商品 16')
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.locator(rowSelector)).toHaveCount(20)
})

for (const [width, height] of [
  [1024, 768],
  [1440, 900],
  [1920, 1080],
]) {
  test(
    'nine ranges use the ordered responsive grid at ' + width,
    async ({ page }, info) => {
      await page.setViewportSize({ width, height })
      await open(page)
      await expect(
        page.locator('.product-data-filters__range-help'),
      ).toHaveCount(0)
      expect(
        await page
          .locator('[data-metric-filter]')
          .evaluateAll((elements) =>
            elements.map((element) =>
              element.getAttribute('data-metric-filter'),
            ),
          ),
      ).toEqual(rangeIds)
      await choose(
        page,
        '[data-metric-filter="exposureCount"] .n-base-selection',
        '自定义',
      )
      await page
        .getByRole('textbox', { name: '曝光下限', exact: true })
        .fill('1000')
      const minInput = page.getByRole('textbox', {
        name: '曝光下限',
        exact: true,
      })
      await expect(minInput).toHaveValue('1000')
      const more = page.getByRole('button', {
        name: '更多筛选',
        exact: true,
      })
      await more.click()
      await expect(page.locator('[data-metric-filter]')).toHaveCount(0)
      await more.click()
      await expect(minInput).toHaveValue('1000')
      expect(
        await minInput.evaluate((element) => element.clientWidth),
      ).toBeGreaterThan(50)
      await page.getByRole('button', { name: '查询', exact: true }).click()
      await expect(page.locator(rowSelector).first()).toBeVisible()
      await expect(page.locator('.pagination-bar')).toBeVisible()
      const geometry = await page.evaluate(() => {
        const query = Array.from(
          document.querySelectorAll('.product-data-filters button'),
        ).find((button) => button.textContent?.trim() === '查询')!
        const bounds = query.getBoundingClientRect(),
          grid = document.querySelector(
            '.product-data-filters__more',
          ) as HTMLElement,
          fields = Array.from(
            document.querySelectorAll<HTMLElement>('[data-metric-filter]'),
          ),
          fieldBounds = fields.map((field) => field.getBoundingClientRect())
        return {
          overflow: document.documentElement.scrollWidth > innerWidth,
          queryInViewport: bounds.bottom <= innerHeight,
          display: getComputedStyle(grid).display,
          columns: getComputedStyle(grid)
            .gridTemplateColumns.split(/\s+/)
            .filter(Boolean).length,
          rows: new Set(fieldBounds.map((field) => Math.round(field.y))).size,
          widths: fieldBounds.map((field) => field.width),
          controls: Array.from(
            document.querySelectorAll('[data-metric-filter] .n-base-selection'),
          ).map((element) => ({
            height: element.getBoundingClientRect().height,
            font: getComputedStyle(element).fontSize,
          })),
        }
      })
      expect(geometry.overflow).toBe(false)
      expect(geometry.queryInViewport).toBe(true)
      const expectedColumns = width >= 1601 ? 5 : width >= 1201 ? 4 : 3
      expect(geometry.display).toBe('grid')
      expect(geometry.columns).toBe(expectedColumns)
      expect(geometry.rows).toBe(Math.ceil(9 / expectedColumns))
      expect(
        Math.max(...geometry.widths) - Math.min(...geometry.widths),
      ).toBeLessThan(1)
      expect(geometry.controls).toHaveLength(9)
      expect(
        geometry.controls.every(
          (control) => control.height === 28 && control.font === '12px',
        ),
      ).toBe(true)
      await page.screenshot({
        path: info.outputPath('product-data-filters-' + width + '.png'),
        animations: 'disabled',
      })
    },
  )
}
