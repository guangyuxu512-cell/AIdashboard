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
  const libraryViews = page.getByRole('navigation', { name: '商品库视图' })
  await expect(libraryViews.getByRole('button')).toHaveText([
    '全部商品',
    '采集/导入',
    '分组商品',
  ])
  await libraryViews.getByRole('button', { name: '采集/导入' }).click()
  await expect(page.getByText('未分组', { exact: true }).first()).toBeVisible()
  await libraryViews.getByRole('button', { name: '分组商品' }).click()
  await expect(page.getByLabel('商品分组筛选')).toBeVisible()
  await libraryViews.getByRole('button', { name: '全部商品' }).click()
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

test('product preview exposes three image rows and preserves unknown values', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/products')
  await page
    .getByRole('button', { name: '编辑商品', exact: true })
    .first()
    .click()
  await expect(page.getByText('编辑商品', { exact: true }).last()).toBeVisible()
  const previewDialog = page.locator('.app-dialog')
  await expect
    .poll(async () =>
      Math.round((await previewDialog.boundingBox())?.width ?? 0),
    )
    .toBeGreaterThan(1100)
  expect(
    await previewDialog.getByLabel('编辑商品标题').evaluate((element) => ({
      height: element.getBoundingClientRect().height,
      fontSize: getComputedStyle(element).fontSize,
    })),
  ).toEqual({ height: 34, fontSize: '14px' })
  await expect(
    previewDialog.getByRole('complementary', { name: '当前范围商品列表' }),
  ).toBeVisible()
  await expect(
    previewDialog.locator('.product-preview__image-section h4'),
  ).toHaveText(['主图', 'SKU 图', '详情图'])
  await expect(
    previewDialog
      .locator('.product-preview__image-section')
      .nth(0)
      .locator('.product-preview__image-card'),
  ).toHaveCount(3)
  await expect(
    previewDialog
      .locator('.product-preview__image-section')
      .nth(1)
      .locator('.product-preview__image-card'),
  ).toHaveCount(2)
  await expect(
    previewDialog
      .locator('.product-preview__image-section')
      .nth(2)
      .locator('.product-preview__image-card'),
  ).toHaveCount(2)
  await expect(
    previewDialog.getByRole('button', { name: 'AI改图' }),
  ).toHaveCount(7)
  await expect(
    previewDialog.getByRole('button', { name: 'AI改图' }).first(),
  ).toBeDisabled()
  await expect(
    previewDialog.getByRole('button', { name: 'AI鉴图' }).first(),
  ).toBeDisabled()
  await expect(
    previewDialog.getByLabel('source:3832497447662387000-sku-a 颜色值'),
  ).toHaveValue('本色')
  await expect(previewDialog.getByText('平台展示：库存紧张')).toBeVisible()
  await page.locator('.app-dialog').getByText('资料包', { exact: true }).click()
  await expect(page.getByText(/\.origin\.txt/)).toBeVisible()
  await expect(page.getByText(/清洗后的兼容文本/)).not.toBeVisible()
})

test('product edit draft saves in Mock, cancels safely and protects unsaved close', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/#/products')
  await page
    .getByRole('button', { name: '编辑商品', exact: true })
    .first()
    .click()
  const previewDialog = page.locator('.app-dialog')

  const title = previewDialog.getByLabel('编辑商品标题')
  await title.fill('不会保存的临时标题')
  await previewDialog.getByRole('button', { name: '新增 SKU' }).click()
  await expect(
    previewDialog
      .locator('.product-preview__image-section')
      .nth(1)
      .locator('.product-preview__image-card'),
  ).toHaveCount(3)
  await previewDialog.getByRole('button', { name: '取消编辑' }).click()
  await expect(previewDialog.getByText('不会保存的临时标题')).toHaveCount(0)
  await expect(
    previewDialog.getByRole('heading', { name: /家用多规格不锈钢/ }),
  ).toBeVisible()
  await expect(
    previewDialog
      .locator('.product-preview__image-section')
      .nth(1)
      .locator('.product-preview__image-card'),
  ).toHaveCount(2)

  await previewDialog.getByRole('button', { name: '编辑商品资料' }).click()
  await title.fill('演示编辑版不锈钢储油罐')
  await previewDialog.getByLabel('SKU 规格维度 1').fill('表面颜色')
  await previewDialog
    .getByLabel('source:3832497447662387000-sku-a SKU 名称')
    .fill('原色标准款')
  await previewDialog
    .getByLabel('source:3832497447662387000-sku-a 表面颜色值')
    .fill('原色')
  await previewDialog
    .getByLabel('source:3832497447662387000-sku-a 当前价格')
    .fill('25.80')
  await previewDialog
    .getByRole('button', { name: '删除 SKU 原色标准款' })
    .click()
  await previewDialog.getByRole('button', { name: '新增 SKU' }).click()
  const newSkuName = previewDialog.getByLabel(/draft-sku-\d+ SKU 名称/)
  await newSkuName.fill('前端新增测试款')
  await previewDialog.getByLabel(/draft-sku-\d+ 表面颜色值/).fill('新增色')
  await previewDialog.getByLabel(/draft-sku-\d+ 规格值/).fill('新增规格')
  await previewDialog.getByLabel(/draft-sku-\d+ 当前价格/).fill('49.90')
  const skuImages = previewDialog
    .locator('.product-preview__image-section')
    .nth(1)
    .locator('.product-preview__image-card')
  await expect(skuImages).toHaveCount(2)
  await expect(skuImages.nth(0)).toContainText('升级款')
  await expect(skuImages.nth(1)).toContainText('前端新增测试款')
  await expect(skuImages.nth(1)).toContainText('尚未绑定图片')
  await previewDialog.getByText('商品属性', { exact: true }).click()
  await previewDialog.getByLabel('属性 1 值').fill('食品级不锈钢')
  await previewDialog.getByRole('button', { name: '保存编辑' }).click()

  await expect(page.getByText(/已保存到当前演示会话/)).toBeVisible()
  await expect(title).toHaveValue('演示编辑版不锈钢储油罐')
  await expect(
    previewDialog.getByText('演示编辑版', { exact: true }),
  ).toBeVisible()
  await previewDialog.getByText('SKU', { exact: true }).click()
  await expect(previewDialog.getByLabel(/draft-sku-\d+ SKU 名称/)).toHaveValue(
    '前端新增测试款',
  )
  await expect(
    previewDialog.getByLabel(/draft-sku-\d+ 表面颜色值/),
  ).toHaveValue('新增色')
  await expect(previewDialog.getByLabel(/draft-sku-\d+ 当前价格/)).toHaveValue(
    '49.90',
  )
  await expect(
    previewDialog.getByText('前端新增（无平台源 ID）', { exact: true }).first(),
  ).toBeVisible()
  await previewDialog.getByText('商品属性', { exact: true }).click()
  await expect(previewDialog.getByLabel('属性 1 值')).toHaveValue(
    '食品级不锈钢',
  )

  await title.fill('未保存关闭测试')
  await previewDialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByText('放弃未保存的修改？')).toBeVisible()
  await page.getByRole('button', { name: '继续编辑' }).click()
  await expect(title).toHaveValue('未保存关闭测试')
  await previewDialog.getByRole('button', { name: '取消编辑' }).click()
  await previewDialog.getByRole('button', { name: '关闭', exact: true }).click()

  await expect(
    page
      .locator('.product-library-title')
      .first()
      .getByText('演示编辑版不锈钢储油罐'),
  ).toBeVisible()
  await page
    .getByRole('button', { name: '编辑商品', exact: true })
    .first()
    .click()
  await expect(page.locator('.app-dialog')).toContainText(
    '演示编辑版不锈钢储油罐',
  )
  await page.locator('.app-dialog').getByText('SKU', { exact: true }).click()
  await expect(
    page.locator('.app-dialog').getByLabel(/draft-sku-\d+ SKU 名称/),
  ).toHaveValue('前端新增测试款')
})

test('product navigation stays inside the current filtered page', async ({
  page,
}) => {
  await page.goto('/#/products')
  await page
    .getByRole('button', { name: '编辑商品', exact: true })
    .first()
    .click()
  const dialog = page.locator('.app-dialog')
  await expect(dialog.getByText('当前视图 1/36')).toBeVisible()
  const navigator = dialog.getByRole('complementary', {
    name: '当前范围商品列表',
  })
  await expect(
    navigator.locator('.product-preview__navigator-item'),
  ).toHaveCount(20)
  await navigator
    .getByRole('button', { name: /^演示商品资料 2 拼多多 · 测试款$/ })
    .click()
  await expect(dialog.getByText('当前视图 2/36')).toBeVisible()
  await dialog.getByRole('button', { name: '下一件' }).click()
  await expect(dialog.getByText('当前视图 3/36')).toBeVisible()
  await expect(dialog.getByLabel('编辑商品标题')).toHaveValue('演示商品资料 3')
  await dialog.getByRole('button', { name: '上一件' }).click()
  await expect(dialog.getByText('当前视图 2/36')).toBeVisible()
  await expect(dialog.getByLabel('编辑商品标题')).toHaveValue('演示商品资料 2')
})

test('product navigation remains reachable after deep editor scrolling', async ({
  page,
}, testInfo) => {
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1366, height: 768 },
    { width: 1024, height: 640 },
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/#/products')
    await page
      .getByRole('button', { name: '编辑商品', exact: true })
      .first()
      .click()
    const dialog = page.locator('.app-dialog')
    await expect(dialog).not.toHaveClass(/transition-enter-active/)
    const navigator = dialog.getByRole('complementary', {
      name: '当前范围商品列表',
    })
    const contentScroll = dialog.locator('.product-preview__content')
    const navigatorList = dialog.locator('.product-preview__navigator-list')
    await expect(contentScroll).toHaveCount(1)
    await expect(navigatorList).toHaveCount(1)

    const overlayHost = page.locator('#app-overlay-host')
    const [hostBox, dialogBox, contentBox, navigatorBox] = await Promise.all([
      overlayHost.boundingBox(),
      dialog.boundingBox(),
      contentScroll.boundingBox(),
      navigator.boundingBox(),
    ])
    expect(hostBox).not.toBeNull()
    expect(dialogBox).not.toBeNull()
    expect(contentBox).not.toBeNull()
    expect(navigatorBox).not.toBeNull()
    expect(dialogBox!.width).toBeGreaterThanOrEqual(hostBox!.width - 32)
    expect(dialogBox!.height).toBeGreaterThanOrEqual(hostBox!.height - 32)
    expect(navigatorBox!.width).toBeGreaterThanOrEqual(300)
    expect(contentBox!.x + contentBox!.width).toBeLessThanOrEqual(
      navigatorBox!.x,
    )
    await page.screenshot({
      path: testInfo.outputPath(
        `04-商品编辑-${viewport.width}x${viewport.height}-顶部.png`,
      ),
      animations: 'disabled',
    })

    const contentMetrics = await contentScroll.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    const navigatorMetrics = await navigatorList.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    expect(contentMetrics.scrollHeight).toBeGreaterThan(
      contentMetrics.clientHeight,
    )
    expect(navigatorMetrics.scrollHeight).toBeGreaterThan(
      navigatorMetrics.clientHeight,
    )

    await contentScroll.evaluate((element) => {
      element.scrollTop = element.scrollHeight
      element.dispatchEvent(new Event('scroll'))
    })
    await expect(navigator).toBeInViewport({ ratio: 1 })
    await expect(dialog.getByRole('button', { name: '保存编辑' })).toBeVisible()
    await expect(
      dialog.getByRole('button', { name: '关闭', exact: true }),
    ).toBeVisible()
    const skuTableScroller = dialog
      .locator(
        '.product-preview__tabs .n-data-table-base-table-body .n-scrollbar-container',
      )
      .first()
    await expect(skuTableScroller).toBeVisible()
    await skuTableScroller.evaluate((element) => {
      element.scrollLeft = element.scrollWidth
      element.dispatchEvent(new Event('scroll'))
    })
    const priceInput = dialog.getByLabel(/当前价格/).first()
    await expect(priceInput).toBeVisible()
    const priceBox = await priceInput.boundingBox()
    expect(priceBox).not.toBeNull()
    expect(priceBox!.x).toBeGreaterThanOrEqual(contentBox!.x)
    expect(priceBox!.x + priceBox!.width).toBeLessThanOrEqual(
      contentBox!.x + contentBox!.width,
    )
    await page.screenshot({
      path: testInfo.outputPath(
        `05-商品编辑-${viewport.width}x${viewport.height}-深滚.png`,
      ),
      animations: 'disabled',
    })
    const secondProduct = navigator.getByRole('button', {
      name: /^演示商品资料 2 拼多多 · 测试款$/,
    })
    await expect(secondProduct).toBeVisible()
    await secondProduct.click()
    await expect(dialog.getByText('当前视图 2/36')).toBeVisible()
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).toBeHidden()
  }
})

test('product library renders fixed views and editable SKU state', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1920, height: 1200 })
  await page.goto('/#/products')
  const views = page.getByRole('navigation', { name: '商品库视图' })
  await views.getByRole('button', { name: '分组商品' }).click()
  await expect(page.getByLabel('商品分组筛选')).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('01-商品库三视图与分组筛选.png'),
    animations: 'disabled',
  })

  await page
    .getByRole('button', { name: '编辑商品', exact: true })
    .first()
    .click()
  const dialog = page.locator('.app-dialog')
  await expect(dialog.getByLabel('编辑商品标题')).toBeVisible()
  await expect(
    dialog.getByRole('complementary', { name: '当前范围商品列表' }),
  ).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('02-近全视口商品编辑与整列导航.png'),
    animations: 'disabled',
  })

  await dialog.getByText('SKU', { exact: true }).click()
  await dialog.getByRole('button', { name: '新增 SKU' }).click()
  await dialog.getByLabel(/draft-sku-\d+ SKU 名称/).fill('前端新增展示款')
  await dialog.getByLabel(/draft-sku-\d+ 颜色值/).fill('展示色')
  await dialog.getByLabel(/draft-sku-\d+ 规格值/).fill('展示规格')
  await dialog.getByLabel(/draft-sku-\d+ 当前价格/).fill('39.90')
  await page.screenshot({
    path: testInfo.outputPath('03-SKU新增删除与规格价格.png'),
    animations: 'disabled',
  })
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
      .getByRole('button', { name: '编辑商品', exact: true })
      .first()
      .click()
    await expect(
      page.getByText('编辑商品', { exact: true }).last(),
    ).toBeVisible()
    const dialog = page.locator('.app-dialog')
    await expect(dialog).not.toHaveClass(/transition-enter-active/)
    const hostBox = await page.locator('#app-overlay-host').boundingBox()
    const box = await dialog.boundingBox()
    expect(hostBox).not.toBeNull()
    expect(box?.width).toBeGreaterThanOrEqual(hostBox!.width - 32)
    expect(box?.width).toBeLessThanOrEqual(hostBox!.width)
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
