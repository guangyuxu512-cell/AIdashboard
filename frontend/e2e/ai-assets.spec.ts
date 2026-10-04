import { expect, test, type Locator, type Page } from '@playwright/test'

async function expectRoleTotal(
  page: Page,
  label: '商品素材' | '复刻参考' | 'AI成品',
  total: number,
): Promise<void> {
  const roleButton = page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: `${label} ${total}` })
  await expect(roleButton).toBeVisible()
  await roleButton.click()
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(
    Math.min(total, 20),
  )
}

async function selectPage(pagination: Locator, pageNumber: number) {
  await pagination
    .locator('.n-pagination-item')
    .filter({ hasText: new RegExp(`^${pageNumber}$`) })
    .click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText(
    String(pageNumber),
  )
}

function selectedOptions(page: Page): Locator {
  return page.locator(
    '.n-base-select-menu:visible .n-base-select-option--selected',
  )
}

test('completes the AI assets library V1 visual interactions', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.addInitScript(() => {
    const nativeClick = HTMLAnchorElement.prototype.click
    HTMLAnchorElement.prototype.click = function () {
      if (this.download) {
        const target = window as typeof window & { __mockDownloads?: string[] }
        target.__mockDownloads ??= []
        target.__mockDownloads.push(this.download)
        return
      }
      nativeClick.call(this)
    }
  })

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/assets?visualMock=1')

  // 1. 素材库入口与 Visual Mock 正常打开。
  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(
    moduleNavigation.getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'true')

  const productFolders = page.getByRole('region', { name: '产品文件夹' })
  const folderRows = productFolders.locator('.product-material-sidebar__item')

  // 2-4. 左侧只呈现统一 Folder Line Icon，不再呈现缩略图槽或第二行身份字段。
  await expect(productFolders.locator('img')).toHaveCount(0)
  await expect(
    productFolders.locator('.product-material-sidebar__identity'),
  ).toHaveCount(0)
  await expect(productFolders.locator('svg.lucide-folder')).toHaveCount(5)

  // 5. 每个文件夹行使用相同的全局固定高度。
  const initialHeights = await folderRows.evaluateAll((rows) =>
    rows.map((row) => row.getBoundingClientRect().height),
  )
  expect(new Set(initialHeights)).toEqual(new Set([51]))

  // 6. 新建只包含名称；超长名称保持单行省略且不改变行高或左栏宽度。
  const longProductName =
    '超长产品名称用于验证文件夹列表始终保持单行省略并且不会撑高行或撑宽侧栏'
  await page.getByRole('button', { name: '新建产品' }).click()
  const createDialog = page.getByRole('dialog').filter({ hasText: '新建产品' })
  await expect(createDialog.locator('input')).toHaveCount(1)
  await createDialog.getByPlaceholder('请输入产品名称').fill(longProductName)
  await createDialog.getByRole('button', { name: '创建' }).click()
  const longRow = productFolders.locator(
    '.product-material-sidebar__item[data-product-id^="visual-product-"]',
  )
  await expect(longRow).toBeVisible()
  const longNameLayout = await longRow.evaluate((row) => {
    const name = row.querySelector<HTMLElement>('.compact-entity-row__title')!
    const styles = getComputedStyle(name)
    return {
      rowHeight: row.getBoundingClientRect().height,
      rowOverflow: row.scrollWidth > row.clientWidth,
      nameOverflow: name.scrollWidth > name.clientWidth,
      whiteSpace: styles.whiteSpace,
      overflow: styles.overflow,
      textOverflow: styles.textOverflow,
    }
  })
  expect(longNameLayout).toEqual({
    rowHeight: 51,
    rowOverflow: false,
    nameOverflow: true,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  })

  // 7. 回到手机支架，商品素材总数 31 且首屏只显示 20 张。
  await page.getByRole('button', { name: '选择产品 手机支架' }).click()
  await expect(
    page.getByRole('button', { name: '选择产品 手机支架' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expectRoleTotal(page, '商品素材', 31)
  await expectRoleTotal(page, '复刻参考', 3)
  await expectRoleTotal(page, 'AI成品', 6)
  await expect(
    page.getByRole('navigation', { name: '素材角色' }),
  ).toHaveAttribute('data-appearance', 'bare')
  await expect(page.getByRole('button', { name: '上传素材' })).toBeDisabled()
  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: '商品素材 31' })
    .click()

  const settings = page.getByRole('region', { name: '产品设置' })
  const normalTemplate = settings.locator('.n-select').nth(0)
  const styleTemplate = settings.locator('.n-select').nth(1)

  // 8. 普通生图为多选，初始至少绑定两组并可继续追加。
  await normalTemplate.click()
  let selectMenu = page.locator('.n-base-select-menu:visible')
  await expect(selectMenu.getByText('竞品复刻 A', { exact: true })).toHaveCount(
    0,
  )
  await expect(selectedOptions(page)).toHaveCount(2)
  await selectMenu.getByText('极简主图组', { exact: true }).click()
  await expect(selectedOptions(page)).toHaveCount(3)
  await page.keyboard.press('Escape')

  // 9-10. 风格复刻为独立多选，两类选项互不交叉。
  await styleTemplate.click()
  selectMenu = page.locator('.n-base-select-menu:visible')
  await expect(
    selectMenu.getByText('电商标准套图 A', { exact: true }),
  ).toHaveCount(0)
  await expect(selectedOptions(page)).toHaveCount(2)
  await selectMenu.getByText('极简风格复刻', { exact: true }).click()
  await expect(selectedOptions(page)).toHaveCount(3)
  await page.keyboard.press('Escape')

  // 11. 商品素材默认 20 / 页，并完整复用 PC 标准分页规格。
  const libraryPanel = page.getByRole('region', { name: '当前产品素材' })
  const pagination = libraryPanel.locator('.ai-assets-workspace__pagination')
  await expect(pagination).toContainText('共 31 条')
  await expect(pagination).toContainText('20 / 页')

  const pageSizePicker = pagination.locator('.n-select')
  await pageSizePicker.click()
  let pageSizeMenu = page.locator('.n-base-select-menu:visible')
  for (const size of [10, 20, 50, 100]) {
    await expect(
      pageSizeMenu.getByText(`${size} / 页`, { exact: true }),
    ).toBeVisible()
  }
  await page.keyboard.press('Escape')

  await selectPage(pagination, 2)
  await pageSizePicker.click()
  pageSizeMenu = page.locator('.n-base-select-menu:visible')
  await pageSizeMenu.getByText('10 / 页', { exact: true }).click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(pagination).toContainText('共 31 条')
  await expect(pagination).toContainText('10 / 页')
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(10)
  await expect(
    pagination.locator('.n-pagination-item').filter({ hasText: /^4$/ }),
  ).toBeVisible()

  await pageSizePicker.click()
  pageSizeMenu = page.locator('.n-base-select-menu:visible')
  await pageSizeMenu.getByText('20 / 页', { exact: true }).click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(pagination).toContainText('20 / 页')
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(20)

  // 12-14. 默认无卡片 Checkbox；普通点击打开详情，选择模式改为整卡切换。
  const batchToolbar = libraryPanel.getByLabel('素材批量操作')
  const assetCards = libraryPanel.locator('button.material-asset-card')
  const selectedCards = libraryPanel.locator(
    'button.material-asset-card[data-selected="true"]',
  )
  await expect(assetCards).toHaveCount(20)
  await expect(
    assetCards.locator('.material-asset-card__checkbox'),
  ).toHaveCount(0)
  await expect(
    libraryPanel.getByRole('checkbox', { name: /^选择素材 / }),
  ).toHaveCount(0)

  await assetCards.first().click()
  const inspector = page.getByRole('region', { name: '素材详情' })
  await expect(inspector).toBeVisible()
  await inspector.getByRole('button', { name: '返回产品设置' }).click()

  const cardLayoutBefore = await assetCards.evaluateAll((cards) =>
    cards.slice(0, 3).map((card) => {
      const preview = card.querySelector<HTMLElement>(
        '.material-asset-card__preview',
      )!
      const caption = card.querySelector<HTMLElement>(
        '.material-asset-card__name',
      )!
      return {
        width: card.getBoundingClientRect().width,
        height: card.getBoundingClientRect().height,
        previewRatio:
          preview.getBoundingClientRect().width /
          preview.getBoundingClientRect().height,
        captionHeight: caption.getBoundingClientRect().height,
      }
    }),
  )
  await batchToolbar.getByRole('button', { name: '选择', exact: true }).click()
  const selectableCards = libraryPanel.getByRole('button', {
    name: /^选择素材 /,
  })
  await expect(selectableCards).toHaveCount(20)
  for (let index = 0; index < 3; index += 1) {
    await selectableCards.nth(index).click()
  }
  await expect(inspector).toHaveCount(0)
  await expect(page.getByRole('region', { name: '产品设置' })).toBeVisible()
  await expect(selectedCards).toHaveCount(3)
  for (let index = 0; index < 3; index += 1) {
    await expect(assetCards.nth(index)).toHaveClass(
      /material-asset-card--selected/,
    )
  }
  const cardLayoutAfter = await assetCards.evaluateAll((cards) =>
    cards.slice(0, 3).map((card) => {
      const preview = card.querySelector<HTMLElement>(
        '.material-asset-card__preview',
      )!
      const caption = card.querySelector<HTMLElement>(
        '.material-asset-card__name',
      )!
      return {
        width: card.getBoundingClientRect().width,
        height: card.getBoundingClientRect().height,
        previewRatio:
          preview.getBoundingClientRect().width /
          preview.getBoundingClientRect().height,
        captionHeight: caption.getBoundingClientRect().height,
      }
    }),
  )
  expect(cardLayoutAfter).toEqual(cardLayoutBefore)

  await selectableCards.first().click()
  await expect(batchToolbar).toContainText('已选 2')
  await expect(assetCards.first()).not.toHaveClass(
    /material-asset-card--selected/,
  )
  await selectableCards.first().click()
  const selectAll = batchToolbar.getByRole('checkbox', { name: '全选' })
  await expect(batchToolbar).toContainText('已选 3')
  await expect(selectAll).toHaveAttribute('aria-checked', 'mixed')

  // 16. 批量下载入口触发当前三张素材的浏览器下载动作。
  await batchToolbar.getByRole('button', { name: '批量下载' }).click()
  await expect(
    page.getByText('已开始下载 3 个素材', { exact: true }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () =>
        (window as typeof window & { __mockDownloads?: string[] })
          .__mockDownloads?.length,
    ),
  ).toBe(3)

  await selectAll.click()
  await expect(selectAll).toBeChecked()
  await expect(batchToolbar).toContainText('已选 20')
  await selectAll.click()
  await expect(batchToolbar).toContainText('已选 0')
  await batchToolbar.getByRole('button', { name: '完成' }).click()
  await expect(
    batchToolbar.getByRole('button', { name: '选择', exact: true }),
  ).toBeVisible()
  await expect(selectedCards).toHaveCount(0)

  // 18-20. 换页清空选择；切 Role 回第一页且不保留跨上下文选择。
  await batchToolbar.getByRole('button', { name: '选择', exact: true }).click()
  await selectableCards.first().click()
  await selectPage(pagination, 2)
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(11)
  await expect(
    batchToolbar.getByRole('button', { name: '选择', exact: true }),
  ).toBeVisible()
  await expect(selectedCards).toHaveCount(0)
  await batchToolbar.getByRole('button', { name: '选择', exact: true }).click()
  await page
    .getByRole('button', { name: /^选择素材 / })
    .first()
    .click()
  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: '复刻参考 3' })
    .click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(
    batchToolbar.getByRole('button', { name: '选择', exact: true }),
  ).toBeVisible()
  await expect(selectedCards).toHaveCount(0)
  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: '商品素材 31' })
    .click()

  // 搜索从第二页重置到第一页，并基于搜索结果重新计算分页。
  await selectPage(pagination, 2)
  await page.getByPlaceholder('搜索素材').fill('商品素材-30')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(1)
  await page.getByPlaceholder('搜索素材').clear()

  // 15. 删除第二页全部 11 张后，总数更新并自动回到上一有效页。
  await selectPage(pagination, 2)
  await selectAll.click()
  await expect(batchToolbar).toContainText('已选 11')
  await batchToolbar.getByRole('button', { name: '批量删除' }).click()
  const batchDeleteDialog = page
    .getByRole('dialog')
    .filter({ hasText: '批量删除素材' })
  await expect(batchDeleteDialog).toContainText('已选择的 11 个素材')
  await batchDeleteDialog.getByRole('button', { name: '删除' }).click()
  await expect(pagination).toContainText('共 20 条')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(batchToolbar).toContainText('已选 0')
  await batchToolbar.getByRole('button', { name: '完成' }).click()
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(20)

  // 17. 单张下载从 Asset Inspector 触发独立下载动作。
  await page
    .getByRole('button', { name: /^查看素材 / })
    .first()
    .click()
  await inspector.getByRole('button', { name: /^下载素材 / }).click()
  await expect(page.getByText('已开始下载', { exact: true })).toBeVisible()
  expect(
    await page.evaluate(
      () =>
        (window as typeof window & { __mockDownloads?: string[] })
          .__mockDownloads?.length,
    ),
  ).toBe(4)
  await inspector.getByRole('button', { name: '返回产品设置' }).click()

  // 产品切换与搜索都清空选择；搜索从第二页重置到第一页。
  await batchToolbar.getByRole('button', { name: '选择', exact: true }).click()
  await page
    .getByRole('button', { name: /^选择素材 / })
    .first()
    .click()
  await page.getByRole('button', { name: '选择产品 马克杯' }).click()
  await expect(
    batchToolbar.getByRole('button', { name: '选择', exact: true }),
  ).toBeVisible()
  await expect(selectedCards).toHaveCount(0)
  await page.getByRole('button', { name: '选择产品 手机支架' }).click()
  await page.getByPlaceholder('搜索素材').fill('正面.jpg')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(1)
  await page.getByPlaceholder('搜索素材').clear()

  // Grid 是唯一中间滚动区，滚动前后 Pagination Y 坐标不变且仍位于容器底部。
  const assetScroll = libraryPanel.locator('.ai-assets-workspace__asset-scroll')
  const footerYBefore = (await pagination.boundingBox())!.y
  await assetScroll.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  const footerYAfter = (await pagination.boundingBox())!.y
  const fixedFooterLayout = await libraryPanel.evaluate((panel) => {
    const grid = panel.querySelector<HTMLElement>(
      '.ai-assets-workspace__asset-scroll',
    )!
    const footer = panel.querySelector<HTMLElement>(
      '.ai-assets-workspace__pagination',
    )!
    return {
      gridOverflowY: getComputedStyle(grid).overflowY,
      footerVisible:
        footer.getBoundingClientRect().bottom <=
        panel.getBoundingClientRect().bottom,
      footerAfterGrid:
        footer.getBoundingClientRect().top >=
        grid.getBoundingClientRect().bottom,
    }
  })
  expect(footerYAfter).toBe(footerYBefore)
  expect(fixedFooterLayout).toEqual({
    gridOverflowY: 'auto',
    footerVisible: true,
    footerAfterGrid: true,
  })

  const layout = await page.evaluate(() => {
    const main = document.querySelector<HTMLElement>('.app-shell__content')
    return {
      documentHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
      bodyOverflow: getComputedStyle(document.body).overflow,
      mainHorizontalOverflow: main ? main.scrollWidth > main.clientWidth : true,
    }
  })
  expect(layout).toEqual({
    documentHorizontalOverflow: false,
    bodyHorizontalOverflow: false,
    bodyOverflow: 'hidden',
    mainHorizontalOverflow: false,
  })
  expect(runtimeErrors).toEqual([])
})

test('renders folder, selection, multi-select and pagination states in both themes', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/assets?visualMock=1')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText('午夜青', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('svg.lucide-folder').first()).toBeVisible()
  await expect(page.getByRole('checkbox', { name: '全选' })).toBeVisible()
  const cards = page.locator('button.material-asset-card')
  await expect(cards.locator('.material-asset-card__checkbox')).toHaveCount(0)
  await page.getByRole('button', { name: '选择', exact: true }).click()
  const selectableCards = page.getByRole('button', { name: /^选择素材 / })
  for (let index = 0; index < 3; index += 1) {
    await selectableCards.nth(index).click()
  }
  await expect(
    page.locator('button.material-asset-card--selected'),
  ).toHaveCount(3)
  await expect(page.getByLabel('素材批量操作')).toContainText('已选 3')
  await expect(page.getByRole('button', { name: '批量下载' })).toBeEnabled()
  await expect(page.getByRole('button', { name: '批量删除' })).toBeEnabled()
  await expect(
    page.getByRole('region', { name: '产品设置' }).locator('.n-select'),
  ).toHaveCount(2)
  await expect(page.locator('.ai-assets-workspace__pagination')).toContainText(
    '共 31 条',
  )

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText('石墨浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(
    page.locator('button.material-asset-card--selected'),
  ).toHaveCount(3)
  await page.getByRole('button', { name: '完成' }).click()
  await expect(
    page.locator('button.material-asset-card--selected'),
  ).toHaveCount(0)
  await page
    .getByRole('button', { name: /^查看素材 / })
    .first()
    .click()
  await expect(page.getByRole('region', { name: '素材详情' })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '选择产品 手机支架' }),
  ).toHaveAttribute('aria-pressed', 'true')
})
