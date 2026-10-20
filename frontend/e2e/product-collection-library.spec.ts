import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

const themes = ['石墨浅色', '森林绿', '珊瑚红', '午夜青'] as const

async function switchTheme(page: Page, label: (typeof themes)[number]) {
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
  await expect(page.locator('.n-dropdown')).toBeHidden()
}

test('collection tasks validate drafts, deduplicate and expose task-only details', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/product-selection?tab=collection-tasks')
  const collectionFilter = page.locator('.collection-task-filter')
  const queryButton = collectionFilter.getByRole('button', {
    name: '查询',
    exact: true,
  })
  const retryButton = collectionFilter.getByRole('button', {
    name: '批量重试',
    exact: true,
  })
  const [queryBounds, retryBounds] = await Promise.all([
    queryButton.boundingBox(),
    retryButton.boundingBox(),
  ])
  expect(queryBounds).not.toBeNull()
  expect(retryBounds).not.toBeNull()
  expect(
    Math.abs(
      queryBounds!.y +
        queryBounds!.height / 2 -
        (retryBounds!.y + retryBounds!.height / 2),
    ),
  ).toBeLessThanOrEqual(1)
  expect(
    await retryButton.evaluate((element) => ({
      height: element.getBoundingClientRect().height,
      fontSize: getComputedStyle(element).fontSize,
    })),
  ).toEqual({ height: 28, fontSize: '12px' })
  await expect(
    page.locator('.collection-tasks-panel .table-toolbar'),
  ).toHaveCount(0)
  const input = page.getByLabel('采集任务输入')
  await input.fill('not-an-id')
  await page.getByRole('button', { name: '创建采集任务' }).click()
  await expect(page.getByText(/无法识别/)).toBeVisible()
  await expect(input).toHaveValue('not-an-id')

  await input.fill('3832497447662387684')
  await page.getByRole('button', { name: '创建采集任务' }).click()
  await expect(page.getByText('已跳过 1 个重复任务')).toBeVisible()
  await expect(input).toHaveValue('3832497447662387684')

  await input.fill('998877665544332211')
  await page.getByRole('button', { name: '创建采集任务' }).click()
  await expect(page.getByText(/演示创建 1 个采集任务/)).toBeVisible()
  await expect(input).toHaveValue('')
  await expect(
    page.getByText('998877665544332211', { exact: true }),
  ).toBeVisible()

  await page.getByRole('button', { name: '详情', exact: true }).first().click()
  await expect(page.getByText('接收回执', { exact: true })).toBeVisible()
  await expect(page.getByText('入库状态', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()

  await page.getByRole('button', { name: '拼多多', exact: true }).click()
  await expect(page.getByText(/手机端手动返回资料/)).toBeVisible()
  await page.getByRole('button', { name: '淘宝', exact: true }).click()
  await expect(page.getByText('淘宝商品资料采集正在规划中。')).toBeVisible()
  await page
    .getByRole('navigation', { name: '采集任务状态' })
    .getByRole('button', { name: /失败 1/ })
    .click()
  await expect(page.getByText('手机端未回传商品资料')).not.toBeVisible()
  await expect(
    page.getByRole('button', { name: '重试', exact: true }),
  ).toBeVisible()
})

test('candidate batch collection appears in the shared mock task workspace', async ({
  page,
}) => {
  await page.goto('/#/product-selection?candidate_size=10')
  await page
    .locator('.candidate-pool .n-data-table-tbody [role="checkbox"]')
    .first()
    .click()
  await page.getByRole('button', { name: '批量采集资料' }).click()
  await expect(page.getByText(/未发起真实采集/)).toBeVisible()
  await page.getByRole('button', { name: '采集任务', exact: true }).click()
  await expect(page.getByText('排队中 1', { exact: false })).toBeVisible()
})

test('product library filters, groups, paging and mock-only file entrances work', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/products')
  await expect(
    page.locator(
      '.product-library-workspace .n-data-table-tbody .n-data-table-tr',
    ),
  ).toHaveCount(20)
  await expect(
    page.locator('.product-library-workspace .n-pagination .n-select'),
  ).toContainText('20 / 页')
  const categoryHeader = page.getByRole('columnheader', { name: '类目' })
  const categoryBounds = await categoryHeader.boundingBox()
  expect(categoryBounds).not.toBeNull()
  expect(Math.round(categoryBounds!.width)).toBe(360)
  const category = page.locator('.product-library-category').first()
  await expect(category).toContainText(
    '家居日用 → 居家布艺 → 防尘罩／空调罩／床头罩',
  )
  expect(
    await categoryHeader.evaluate((element) => ({
      fontSize: getComputedStyle(element).fontSize,
      padding: getComputedStyle(element).padding,
    })),
  ).toEqual({ fontSize: '12px', padding: '8px 12px' })
  await page
    .locator('.product-library-workspace .n-pagination-item')
    .filter({ hasText: /^2$/ })
    .click()
  await expect(page.getByText('演示商品资料 21', { exact: true })).toBeVisible()
  await page
    .locator('.product-library-workspace .n-pagination-item')
    .filter({ hasText: /^1$/ })
    .click()

  const keyword = page.getByPlaceholder('搜索商品标题、商品 ID 或类目')
  await keyword.fill('3832497447662387000')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(
    page.getByText('3832497447662387000', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '重置', exact: true }).click()

  const rowCheckboxes = page.locator(
    '.product-library-workspace .n-data-table-tbody [role="checkbox"]',
  )
  await rowCheckboxes.nth(0).click()
  await rowCheckboxes.nth(1).click()
  await expect(page.getByText('已选 2 项')).toBeVisible()
  await page.getByRole('button', { name: '批量导出 TXT' }).click()
  await expect(page.getByText('批量商品导出 ZIP')).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()

  await page.getByRole('button', { name: '移动分组' }).first().click()
  await expect(page.getByText('新分组名称')).toBeVisible()
  const groupDialog = page.locator('.app-dialog').filter({
    has: page.getByPlaceholder('新分组名称'),
  })
  await groupDialog.locator('.n-base-selection').click()
  const groupMenu = page.locator('.app-select-menu--viewport-safe:visible')
  await expect(groupMenu).toBeVisible()
  expect(
    await groupMenu.evaluate(
      (element) =>
        !!element.closest('#app-overlay-host') &&
        !element.closest('.app-dialog'),
    ),
  ).toBe(true)
  await page.keyboard.press('Escape')
  await page.getByPlaceholder('新分组名称').fill('本轮演示组')
  await page
    .locator('.app-dialog')
    .getByRole('button', { name: '新建分组' })
    .click()
  await expect(page.getByText(/已创建演示分组/)).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()

  await page.getByRole('button', { name: '导入资料包' }).click()
  const importDialog = page.locator('.app-dialog')
  await expect(
    importDialog.getByText('TXT 文件', { exact: true }),
  ).toBeVisible()
  const fileInputs = importDialog.locator('input[type="file"]')
  await fileInputs.nth(0).setInputFiles({
    name: '3832497447662387000.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('mock cleaned txt'),
  })
  await expect(importDialog.getByText(/3832497447662387000\.txt/)).toBeVisible()
  await importDialog.getByRole('button', { name: '确认演示' }).click()
  await expect(page.getByText(/未解析或写入商品库/)).toBeVisible()

  await page.getByRole('button', { name: '导入资料包' }).click()
  const reopened = page.locator('.app-dialog')
  await reopened.getByText('ZIP 包', { exact: true }).click()
  await expect(page.getByRole('button', { name: '选择ZIP 包' })).toBeVisible()
  await reopened
    .locator('input[type="file"]')
    .nth(1)
    .setInputFiles({
      name: 'products.zip',
      mimeType: 'application/zip',
      buffer: Buffer.from('mock zip'),
    })
  await expect(reopened.getByText(/products\.zip/)).toBeVisible()
  await reopened.getByText('文件夹', { exact: true }).click()
  await expect(page.getByRole('button', { name: '选择文件夹' })).toBeVisible()
  await reopened
    .locator('input[type="file"]')
    .nth(2)
    .setInputFiles(
      path.resolve('src/features/product-selection/fixtures/photos'),
    )
  await expect(reopened.getByText(/product-1\.webp/)).toBeVisible()
  await expect(reopened.getByText(/product-2\.webp/)).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()
})

test('product preview switches images and preserves unknown values', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/products')
  await page.getByRole('button', { name: '预览', exact: true }).first().click()
  await expect(page.getByText('商品资料预览')).toBeVisible()
  const previewDialog = page.locator('.app-dialog')
  await expect
    .poll(async () =>
      Math.round((await previewDialog.boundingBox())?.width ?? 0),
    )
    .toBe(960)
  expect(
    await previewDialog
      .getByRole('button', { name: 'AI 改图' })
      .evaluate((element) => ({
        height: element.getBoundingClientRect().height,
        fontSize: getComputedStyle(element).fontSize,
      })),
  ).toEqual({ height: 34, fontSize: '14px' })
  await expect(page.getByRole('button', { name: 'AI 改图' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'AI 审图' })).toBeDisabled()
  await page.getByRole('button', { name: '详情图', exact: true }).click()
  await expect(page.locator('.product-preview__thumbnails button')).toHaveCount(
    2,
  )
  const skuRows = page.locator('.app-dialog .product-preview__sku')
  await expect(skuRows.first()).toContainText('—')
  await expect(skuRows.nth(1)).toContainText('平台展示：库存紧张')
  await page.locator('.app-dialog').getByText('资料包', { exact: true }).click()
  await expect(page.getByText(/\.origin\.txt/)).toBeVisible()
  await expect(page.getByText(/清洗后的兼容文本/)).not.toBeVisible()
})

test('shared selects escape both product-group and member-dialog clipping bodies', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 620 })
  await page.goto('/#/products')
  const productRow = page
    .locator('.product-library-workspace .n-data-table-tbody .n-data-table-tr')
    .first()
  await productRow.getByRole('checkbox').click()
  await page.getByRole('button', { name: '移动分组', exact: true }).click()
  let dialog = page.locator('.app-dialog').filter({
    has: page.getByPlaceholder('新分组名称'),
  })
  await dialog.locator('.n-base-selection').click()
  let menu = page.locator('.app-select-menu--viewport-safe:visible')
  await expect(menu).toBeVisible()
  expect(
    await menu.evaluate(
      (element) =>
        !!element.closest('#app-overlay-host') &&
        !element.closest('.app-dialog'),
    ),
  ).toBe(true)
  await page.keyboard.press('Escape')
  await dialog.getByRole('button', { name: '取消', exact: true }).click()

  await page.goto('/#/settings/users')
  await page.getByRole('button', { name: '新增成员', exact: true }).click()
  dialog = page.locator('.app-dialog').filter({ hasText: '新增成员' })
  const teamField = dialog
    .locator('.n-form-item')
    .filter({ hasText: '所属团队（可选）' })
  await teamField.locator('.n-base-selection').click()
  menu = page.locator('.app-select-menu--viewport-safe:visible')
  await expect(menu).toBeVisible()
  expect(
    await menu.evaluate(
      (element) =>
        !!element.closest('#app-overlay-host') &&
        !element.closest('.app-dialog'),
    ),
  ).toBe(true)
  const option = menu.locator('.n-base-select-option').last()
  const optionBounds = await option.boundingBox()
  expect(optionBounds).not.toBeNull()
  expect(
    await page.evaluate(
      ({ x, y }) =>
        !!document.elementFromPoint(x, y)?.closest('.n-base-select-option'),
      {
        x: optionBounds!.x + optionBounds!.width / 2,
        y: optionBounds!.y + optionBounds!.height / 2,
      },
    ),
  ).toBe(true)
})

test('product workspaces remain usable in four themes and narrow viewport', async ({
  page,
}, testInfo) => {
  for (const theme of themes) {
    await page.setViewportSize({ width: 960, height: 720 })
    await page.goto('/#/products')
    await switchTheme(page, theme)
    await expect(page.getByRole('columnheader', { name: '操作' })).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath(`${theme}-商品库.png`),
      animations: 'disabled',
    })
    await page
      .getByRole('button', { name: '预览', exact: true })
      .first()
      .click()
    await expect(page.getByText('商品资料预览')).toBeVisible()
    const dialog = page.locator('.app-dialog')
    const box = await dialog.boundingBox()
    expect(box?.width).toBeLessThanOrEqual(928)
    await page.screenshot({
      path: testInfo.outputPath(`${theme}-商品预览.png`),
      animations: 'disabled',
    })
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await page.goto('/#/product-selection?tab=collection-tasks')
    await expect(
      page.getByRole('button', { name: '创建采集任务' }),
    ).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath(`${theme}-采集任务.png`),
      animations: 'disabled',
    })
  }
})
