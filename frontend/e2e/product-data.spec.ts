import { expect, test, type Page } from '@playwright/test'

async function chooseShop(page: Page, name: string) {
  await page.locator('.product-data-filters .n-base-selection').first().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .getByText(name, { exact: true })
    .last()
    .click()
}
async function settle(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all(
      Array.from(document.images).map((image) =>
        image.decode().catch(() => undefined),
      ),
    )
  })
}
test('inherits the Green candidate compact thumbnail and preserves the default image summary', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/product-selection')
  const thumbnail = page
    .locator('.product-image--thumbnail')
    .first()
    .locator('img')
  await expect(thumbnail).toBeVisible()
  await expect(thumbnail).toHaveAttribute('referrerpolicy', 'no-referrer')
  const size = await thumbnail.boundingBox()
  expect(size?.width).toBe(48)
  expect(size?.height).toBe(48)
  await page.getByRole('button', { name: '详情', exact: true }).first().click()
  const summary = page.locator('.n-drawer .product-image--summary img')
  await expect(summary).toBeVisible()
  const summarySize = await summary.boundingBox()
  expect(summarySize?.width).toBe(80)
  expect(summarySize?.height).toBe(80)
  await settle(page)
  await page.screenshot({
    path: info.outputPath('candidate-image-compatibility.png'),
    animations: 'disabled',
  })
})
test('queries, sorts across pages, configures fields, manages groups from zero and inspects complete product data', async ({
  page,
}, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/product-data')
  const table = page.locator('.product-data-table'),
    rows = table.locator('.n-data-table-tbody .n-data-table-tr')
  await expect(rows).toHaveCount(20)
  await expect(page.getByText('演示数据', { exact: true })).toBeVisible()
  await expect(page.locator('.pagination-bar')).toContainText('共 31 条')
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  await page
    .getByRole('button', { name: '复制商品ID', exact: true })
    .first()
    .click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    '9000000000000000001',
  )
  await page.locator('.pagination-bar').getByText('2', { exact: true }).click()
  await table
    .getByRole('columnheader', { name: '曝光', exact: true })
    .locator('.n-data-table-sorter')
    .click()
  await expect(rows.first()).toContainText('演示商品 18')
  await expect(page.locator('.n-pagination-item--active')).toHaveText('1')
  await page.getByRole('button', { name: '字段配置', exact: true }).click()
  const fields = page
    .locator('.app-dialog')
    .filter({ hasText: '商品信息 / ID · 固定左列' })
  await expect(fields).toContainText('基础字段')
  await expect(fields).toContainText('核心指标')
  await expect(fields).toContainText('交易指标')
  await expect(fields).toContainText('流量指标')
  await expect(fields).not.toContainText('结算金额')
  await expect(fields).not.toContainText('实时可售库存')
  await fields.getByRole('checkbox', { name: '点击人数', exact: true }).click()
  const selectedFields = fields.locator('.product-fields__selected-item')
  await expect(selectedFields.last()).toHaveAttribute(
    'data-field-id',
    'product_click_ucnt',
  )
  await fields
    .locator('[data-field-id="clickCount"]')
    .dragTo(fields.locator('[data-field-id="shop"]'), {
      targetPosition: { x: 20, y: 2 },
    })
  await expect(selectedFields.first()).toHaveAttribute(
    'data-field-id',
    'clickCount',
  )
  await fields.getByRole('button', { name: '保存', exact: true }).click()
  const clickCountHeader = table.getByRole('columnheader', {
      name: '点击量',
      exact: true,
    }),
    clickUsersHeader = table.getByRole('columnheader', {
      name: '点击人数',
      exact: true,
    }),
    shopHeader = table.getByRole('columnheader', { name: '店铺', exact: true }),
    exposureHeader = table.getByRole('columnheader', {
      name: '曝光',
      exact: true,
    })
  await expect(clickUsersHeader).toBeAttached()
  expect((await clickCountHeader.boundingBox())!.x).toBeLessThan(
    (await shopHeader.boundingBox())!.x,
  )
  expect((await shopHeader.boundingBox())!.x).toBeLessThan(
    (await exposureHeader.boundingBox())!.x,
  )
  await page.reload()
  await expect(clickUsersHeader).toBeAttached()
  expect((await clickCountHeader.boundingBox())!.x).toBeLessThan(
    (await shopHeader.boundingBox())!.x,
  )
  await page.getByRole('button', { name: '字段配置', exact: true }).click()
  await fields
    .locator('[data-field-id="shop"]')
    .dragTo(fields.locator('[data-field-id="clickCount"]'), {
      targetPosition: { x: 20, y: 2 },
    })
  await fields.getByRole('button', { name: '取消', exact: true }).click()
  expect((await clickCountHeader.boundingBox())!.x).toBeLessThan(
    (await shopHeader.boundingBox())!.x,
  )
  await page.locator('.pagination-bar').getByText('2', { exact: true }).click()
  await expect(clickUsersHeader).toBeAttached()
  await page.locator('.pagination-bar').getByText('1', { exact: true }).click()
  await chooseShop(page, '星河服饰旗舰店')
  await page.getByText('近7天', { exact: true }).click()
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.locator('.pagination-bar')).toContainText('共 16 条')
  await page.getByRole('button', { name: '分组管理', exact: true }).click()
  const manager = page
    .locator('.app-dialog')
    .filter({ has: page.getByRole('textbox', { name: '分组名称' }) })
  await expect(manager.getByText('暂无分组', { exact: true })).toBeVisible()
  await manager.getByRole('textbox', { name: '分组名称' }).fill('出单款')
  await manager.getByRole('button', { name: '创建分组', exact: true }).click()
  await expect(manager.locator('.product-groups__row')).toContainText('出单款')
  await manager.getByRole('button', { name: '完成', exact: true }).click()
  await rows.first().getByRole('checkbox').click()
  await page.getByRole('button', { name: '批量设置分组', exact: true }).click()
  const batch = page.locator('.app-dialog').filter({ hasText: '已选 1 件商品' })
  await batch.locator('.n-base-selection').click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .getByText('出单款', { exact: true })
    .last()
    .click()
  await batch.getByRole('button', { name: '保存', exact: true }).click()
  await page.getByRole('button', { name: '分组管理', exact: true }).click()
  await expect(manager.locator('.product-groups__row')).toContainText('1')
  await manager.getByRole('button', { name: '重命名', exact: true }).click()
  await manager.getByRole('textbox', { name: '分组名称' }).fill('福利款')
  await manager.getByRole('button', { name: '保存名称', exact: true }).click()
  await expect(manager.locator('.product-groups__row')).toContainText('福利款')
  await manager.getByRole('button', { name: '删除', exact: true }).click()
  const confirmation = page
    .locator('.app-dialog')
    .filter({ hasText: '删除商品分组' })
  await expect(confirmation).toContainText(
    '1 件商品将移至未分组，商品和指标保留',
  )
  await confirmation.getByRole('button', { name: '删除', exact: true }).click()
  await expect(manager.getByText('暂无分组', { exact: true })).toBeVisible()
  await manager.getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.locator('.pagination-bar')).toContainText('共 16 条')
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(page.locator('.n-drawer')).toContainText('核心指标')
  await expect(page.locator('.n-drawer')).toContainText('曝光')
  await expect(page.locator('.n-drawer')).not.toContainText('结算金额')
  await page
    .locator('.n-drawer')
    .getByRole('button', { name: '关闭', exact: true })
    .click()
  await page
    .getByRole('textbox', { name: '商品名称', exact: true })
    .fill('不存在的商品')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(
    page.getByText('所选范围暂无商品数据', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(rows).toHaveCount(20)
  await settle(page)
  await page.screenshot({
    path: info.outputPath('product-data-normal.png'),
    animations: 'disabled',
  })
  expect(errors).toEqual([])
})

test('recovers query error and keeps wide tables and dialogs within ordinary and maximized viewports', async ({
  page,
}, info) => {
  await page.goto('/#/product-data?productDataPreview=query-error')
  await expect(
    page.getByText('演示操作失败，请重试', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(
    page.locator('.product-data-table .n-data-table-tbody .n-data-table-tr'),
  ).toHaveCount(20)
  for (const [width, height] of [
    [1024, 768],
    [1920, 1080],
  ]) {
    await page.setViewportSize({ width, height })
    await page.getByRole('button', { name: '字段配置', exact: true }).click()
    const fields = page.locator('.app-dialog')
    await expect(fields).toBeVisible()
    await expect
      .poll(async () => {
        const bounds = await fields.boundingBox()
        return (
          !!bounds &&
          bounds.y >= 54 &&
          bounds.x >= 0 &&
          bounds.x + bounds.width <= width! &&
          bounds.y + bounds.height <= height!
        )
      })
      .toBe(true)
    for (const checkbox of await fields.getByRole('checkbox').all())
      if (!(await checkbox.isChecked())) await checkbox.click()
    await page.screenshot({
      path: info.outputPath('product-data-fields-' + width + '.png'),
      animations: 'disabled',
    })
    await fields.getByRole('button', { name: '保存', exact: true }).click()
    const overflow = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth > innerWidth,
      table: Array.from(
        document.querySelectorAll('.product-data-table .n-scrollbar-container'),
      ).some((element) => element.scrollWidth > element.clientWidth),
    }))
    expect(overflow).toEqual({ page: false, table: true })
    await expect(page.locator('.pagination-bar')).toBeVisible()
    await settle(page)
    await page.screenshot({
      path: info.outputPath('product-data-' + width + '.png'),
      animations: 'disabled',
    })
  }
})
