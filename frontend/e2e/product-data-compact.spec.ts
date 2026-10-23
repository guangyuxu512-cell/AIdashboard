import { expect, test, type Locator, type Page } from '@playwright/test'

const rowsSelector = '.product-data-table .n-data-table-tbody .n-data-table-tr'
async function measure(locator: Locator) {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element),
      bounds = element.getBoundingClientRect()
    return {
      font: style.fontSize,
      height: bounds.height,
      width: bounds.width,
      padding: style.padding,
      gap: style.gap,
      border: style.borderRightWidth,
      borderStyle: style.borderRightStyle,
    }
  })
}
async function openProducts(page: Page) {
  await page.goto('/#/product-data')
  await expect(page.locator(rowsSelector)).toHaveCount(20)
  await page.evaluate(() => document.fonts.ready)
}
async function chooseSize(page: Page, size: number) {
  await page.locator('.pagination-bar .n-base-selection').click()
  await page
    .locator('.n-base-select-option')
    .filter({
      hasText: new RegExp('^' + size + '\\s*/\\s*页$'),
    })
    .click()
}

for (const [width, height] of [
  [1024, 768],
  [1440, 900],
  [1920, 1080],
]) {
  test('compact product data layout at ' + width, async ({ page }, info) => {
    await page.setViewportSize({ width, height })
    await openProducts(page)
    const card = page.locator('.product-data-view'),
      table = page.locator('.product-data-table'),
      row = page.locator(rowsSelector).first()
    const metrics = {
      card: await measure(card),
      content: await measure(card.locator('.management-list-section__content')),
      header: await measure(table.locator('th').nth(1)),
      productColumn: await measure(row.locator('td').nth(1)),
      row: await measure(row),
      image: await measure(row.locator('.product-image')),
      id: await measure(row.locator('.product-info-cell__id-text')),
      copy: await measure(
        row.getByRole('button', { name: '复制商品ID', exact: true }),
      ),
      query: await measure(
        page.getByRole('button', { name: '查询', exact: true }),
      ),
      input: await measure(
        page.locator('.product-data-filters .n-input').first(),
      ),
      date: await measure(
        page.locator('.product-data-filters .n-radio-button').first(),
      ),
      pagination: await measure(page.locator('.n-pagination-item--active')),
      filter: await measure(
        page.locator('.product-data-filters .filter-bar__fields').first(),
      ),
    }
    await info.attach('compact-geometry-' + width, {
      body: JSON.stringify(metrics, null, 2),
      contentType: 'application/json',
    })
    console.log('PRODUCT_DATA_COMPACT', JSON.stringify({ width, metrics }))
    expect(metrics.card).toMatchObject({ font: '12px', padding: '12px' })
    expect(metrics.content.gap).toBe('8px')
    expect(metrics.filter.gap).toBe('8px')
    expect(metrics.header).toMatchObject({
      font: '12px',
      border: '1px',
      borderStyle: 'solid',
    })
    expect(metrics.productColumn).toMatchObject({
      font: '12px',
      width: 304,
      border: '1px',
    })
    expect(metrics.row.height).toBe(65)
    expect(metrics.image).toMatchObject({ width: 48, height: 48 })
    expect(metrics.id.font).toBe('12px')
    expect(metrics.copy).toMatchObject({ width: 28, height: 28 })
    for (const item of [metrics.query, metrics.input, metrics.date])
      expect(item).toMatchObject({ font: '12px', height: 28 })
    expect(metrics.pagination).toMatchObject({ font: '12px', height: 28 })
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false)
    await page.screenshot({
      path: info.outputPath('product-data-compact-' + width + '.png'),
      animations: 'disabled',
    })
  })
}

for (const [preset, label] of [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
]) {
  test(
    'compact product data theme and teleported menu ' + preset,
    async ({ page }, info) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await openProducts(page)
      await page.getByRole('button', { name: '切换主题', exact: true }).click()
      await page
        .locator('.n-dropdown')
        .getByText(label!, { exact: true })
        .click()
      await expect(page.locator('html')).toHaveAttribute(
        'data-theme-preset',
        preset!,
      )
      const select = page
        .locator('.product-data-filters .n-base-selection')
        .first()
      await expect
        .poll(() => measure(select))
        .toMatchObject({ font: '12px', height: 28 })
      for (const radio of await page
        .locator('.product-data-filters .n-radio-button')
        .all())
        await expect
          .poll(() => measure(radio))
          .toMatchObject({ font: '12px', height: 28 })
      expect(
        await measure(
          page.getByRole('button', { name: '切换主题', exact: true }),
        ),
      ).toMatchObject({ font: '14px', height: 34 })
      await select.click()
      const menu = page.locator('.app-select-menu--viewport-safe:visible'),
        option = menu.locator('.n-base-select-option').first()
      await expect(option).toBeVisible()
      await expect
        .poll(() => measure(option))
        .toMatchObject({ font: '12px', height: 28 })
      expect(
        await menu.evaluate(
          (element) => !!element.closest('.product-data-view'),
        ),
      ).toBe(false)
      expect(
        await menu.evaluate(
          (element) => !!element.closest('#app-overlay-host'),
        ),
      ).toBe(true)
      await page.screenshot({
        path: info.outputPath('product-data-' + preset + '-menu.png'),
        animations: 'disabled',
      })
      await page.keyboard.press('Escape')
      expect(
        await measure(page.locator('.product-data-table th').nth(1)),
      ).toMatchObject({ border: '1px', borderStyle: 'solid' })
    },
  )
}

test('defaults to twenty, changes page size without stale pages and retains the current choice on reset', async ({
  page,
}) => {
  await openProducts(page)
  const rows = page.locator(rowsSelector),
    pagination = page.locator('.pagination-bar')
  await expect(pagination.locator('.n-base-selection')).toContainText(
    /20\s*\/\s*页/,
  )
  await pagination.getByText('2', { exact: true }).click()
  await expect(rows).toHaveCount(11)
  await rows.first().getByRole('checkbox').click()
  await chooseSize(page, 10)
  await expect(rows).toHaveCount(10)
  await expect(page.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(rows.first().getByRole('checkbox')).not.toBeChecked()
  await pagination.getByText('2', { exact: true }).click()
  await chooseSize(page, 50)
  await expect(rows).toHaveCount(31)
  await expect(page.locator('.n-pagination-item--active')).toHaveText('1')
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(rows).toHaveCount(31)
  await expect(pagination.locator('.n-base-selection')).toContainText(
    /50\s*\/\s*页/,
  )
  await page.reload()
  await expect(rows).toHaveCount(20)
})

test('keeps new optional range controls compact without changing date behavior', async ({
  page,
}, info) => {
  await openProducts(page)
  await page.getByRole('button', { name: '更多筛选', exact: true }).click()
  await page
    .locator('[data-metric-filter="exposureCount"] .n-base-selection')
    .click()
  await page
    .locator('.n-base-select-option')
    .getByText('自定义', { exact: true })
    .click()
  await page.locator('.n-radio-button').filter({ hasText: '自定义' }).click()
  const metrics = {
    radio: await measure(
      page.locator('.product-data-filters .n-radio-button').first(),
    ),
    number: await measure(
      page.locator('.product-data-filters__more .n-input').first(),
    ),
    date: await measure(
      page.locator('.product-data-filters .app-date-picker .n-input'),
    ),
  }
  console.log('PRODUCT_DATA_OPTIONAL_FILTERS', JSON.stringify(metrics))
  await info.attach('optional-filter-controls', {
    body: JSON.stringify(metrics, null, 2),
    contentType: 'application/json',
  })
  expect(metrics.number).toMatchObject({ font: '12px', height: 28 })
  expect(metrics.date).toMatchObject({ font: '12px', height: 28 })
  expect(metrics.radio).toMatchObject({ font: '12px', height: 28 })
})

test('keeps overlays and subsequent default pages outside the compact Vue theme boundary', async ({
  page,
}, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 900 })
  await openProducts(page)
  await page.locator('.product-data-filters .n-base-selection').first().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .getByText('星河服饰旗舰店', { exact: true })
    .click()
  await page.getByRole('button', { name: '分组管理', exact: true }).click()
  let dialog = page.locator('.app-dialog')
  await expect(dialog.getByRole('textbox', { name: '分组名称' })).toBeVisible()
  await expect
    .poll(() => measure(dialog.locator('.n-input').first()))
    .toMatchObject({
      font: '14px',
      height: 34,
    })
  expect(
    await measure(
      dialog.getByRole('button', { name: '创建分组', exact: true }),
    ),
  ).toMatchObject({ font: '14px', height: 34 })
  await dialog.getByRole('button', { name: '完成', exact: true }).click()
  await page.getByRole('button', { name: '字段配置', exact: true }).click()
  dialog = page.locator('.app-dialog')
  await expect
    .poll(() =>
      measure(dialog.getByRole('button', { name: '保存', exact: true })),
    )
    .toMatchObject({ font: '14px', height: 34 })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  const row = page.locator(rowsSelector).first()
  await row.getByRole('checkbox').click()
  await page.getByRole('button', { name: '批量设置分组', exact: true }).click()
  dialog = page.locator('.app-dialog')
  await expect
    .poll(() => measure(dialog.locator('.n-base-selection')))
    .toMatchObject({
      font: '14px',
      height: 34,
    })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await row.getByRole('button', { name: '详情', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  await expect(drawer.locator('.product-info-cell')).toBeVisible()
  expect(await measure(drawer.locator('.product-image'))).toMatchObject({
    height: 64,
  })
  expect(
    await measure(drawer.locator('.product-info-cell__title')),
  ).toMatchObject({ font: '14px' })
  expect(
    await measure(drawer.locator('.product-info-cell__id-text')),
  ).toMatchObject({ font: '13px' })
  expect(
    await measure(
      drawer.getByRole('button', { name: '复制商品ID', exact: true }),
    ),
  ).toMatchObject({ height: 30, width: 30 })
  await page.screenshot({
    path: info.outputPath('product-data-default-detail.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('button', { name: '关闭', exact: true }).click()
  await page.goto('/#/shops')
  await expect(page.locator('.product-data-view')).toHaveCount(0)
  await expect(page.locator('.app-table')).toBeVisible()
  expect(await measure(page.locator('.n-input').first())).toMatchObject({
    font: '14px',
    height: 34,
  })
  expect(await measure(page.locator('.app-table th').nth(1))).toMatchObject({
    font: '14px',
    border: '1px',
  })
  await page.goto('/#/product-data')
  await expect(page.locator(rowsSelector)).toHaveCount(20)
  expect(
    await measure(page.locator(rowsSelector).first().locator('.product-image')),
  ).toMatchObject({ height: 48 })
  expect(errors).toEqual([])
})
