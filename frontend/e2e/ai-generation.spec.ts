import { expect, test, type Locator, type Page } from '@playwright/test'

function collectRuntimeErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function chooseSelectOption(
  page: Page,
  control: Locator,
  label: string,
): Promise<void> {
  await control.click()
  await page
    .locator('.n-base-select-menu:visible')
    .getByText(label, { exact: true })
    .click()
}

async function expectBareSwitchBar(control: Locator): Promise<void> {
  await expect(control).toHaveAttribute('data-appearance', 'bare')

  const groupStyle = await control.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      backgroundColor: style.backgroundColor,
      backgroundImage: style.backgroundImage,
      borderTopWidth: style.borderTopWidth,
      borderRightWidth: style.borderRightWidth,
      borderBottomWidth: style.borderBottomWidth,
      borderLeftWidth: style.borderLeftWidth,
      borderRadius: style.borderRadius,
      boxShadow: style.boxShadow,
      paddingTop: style.paddingTop,
      paddingRight: style.paddingRight,
      paddingBottom: style.paddingBottom,
      paddingLeft: style.paddingLeft,
    }
  })

  expect(groupStyle).toEqual({
    backgroundColor: 'rgba(0, 0, 0, 0)',
    backgroundImage: 'none',
    borderTopWidth: '0px',
    borderRightWidth: '0px',
    borderBottomWidth: '0px',
    borderLeftWidth: '0px',
    borderRadius: '0px',
    boxShadow: 'none',
    paddingTop: '0px',
    paddingRight: '0px',
    paddingBottom: '0px',
    paddingLeft: '0px',
  })

  const activeButton = control.locator('button[aria-pressed="true"]')
  const inactiveButtons = control.locator('button[aria-pressed="false"]')
  await expect(activeButton).toHaveCount(1)
  expect(await inactiveButtons.count()).toBeGreaterThan(0)
}

test('keeps every generation short option group unframed in both themes', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')

  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(moduleNavigation).toHaveAttribute('data-appearance', 'framed')

  const workMode = page.getByRole('navigation', { name: '生成工作方式' })
  const instantConfig = page.getByRole('region', { name: '即时生成配置' })
  const instantGroups = [
    workMode,
    instantConfig.getByRole('navigation', { name: '生成模式' }),
    instantConfig.getByRole('navigation', { name: '输出格式' }),
  ]
  for (const group of instantGroups) await expectBareSwitchBar(group)

  await workMode.getByRole('button', { name: '批量生成' }).click()
  await expect(
    workMode.getByRole('button', { name: '批量生成' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    workMode.getByRole('button', { name: '即时生成' }),
  ).toHaveAttribute('aria-pressed', 'false')
  const batchConfig = page.getByRole('region', { name: '批量生成配置' })
  const batchGroups = [
    workMode,
    batchConfig.getByRole('navigation', { name: '批量生成模式' }),
    batchConfig.getByRole('navigation', { name: '产品范围' }),
    batchConfig.getByRole('navigation', { name: '模板来源' }),
    batchConfig.getByRole('navigation', { name: '输出范围' }),
  ]
  for (const group of batchGroups) await expectBareSwitchBar(group)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  for (const group of batchGroups) await expectBareSwitchBar(group)

  await workMode.getByRole('button', { name: '即时生成' }).click()
  const darkInstantConfig = page.getByRole('region', {
    name: '即时生成配置',
  })
  await expectBareSwitchBar(
    darkInstantConfig.getByRole('navigation', { name: '生成模式' }),
  )
  await expectBareSwitchBar(
    darkInstantConfig.getByRole('navigation', { name: '输出格式' }),
  )

  const layout = await page.evaluate(() => ({
    horizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    documentVerticalOverflow:
      document.documentElement.scrollHeight >
      document.documentElement.clientHeight,
  }))
  expect(layout).toEqual({
    horizontalOverflow: false,
    documentVerticalOverflow: false,
  })
  expect(runtimeErrors).toEqual([])
})

test('uses registry-driven input slots and one editable generation config', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')

  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(moduleNavigation.getByRole('button')).toHaveCount(4)
  await expect(
    moduleNavigation.getByRole('button', { name: 'AI生图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  const workMode = page.getByRole('navigation', {
    name: '生成工作方式',
  })
  await expect(
    workMode.getByRole('button', { name: '即时生成' }),
  ).toHaveAttribute('aria-pressed', 'true')

  const config = page.getByRole('region', { name: '即时生成配置' })
  const generationMode = config.getByRole('navigation', { name: '生成模式' })
  await expect(
    generationMode.getByRole('button', { name: '普通生图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(moduleNavigation).toHaveClass(/context-switch-bar/)
  await expect(generationMode).toHaveClass(/context-switch-bar/)

  const productSlot = config.locator('[data-input-slot="PRODUCT_IMAGES"]')
  const productSurface = productSlot.locator('.generation-input-slot__surface')
  await expect(productSlot).toHaveAttribute('aria-label', '商品图片')
  await expect(
    productSurface.getByText('点击上传图片', { exact: true }),
  ).toBeVisible()
  const emptySlotBox = await productSurface.boundingBox()
  expect(emptySlotBox?.height).toBeGreaterThanOrEqual(160)

  const generationConfig = config.getByTestId('instant-generation-config')
  const promptInput = generationConfig.getByLabel('提示词')
  await expect(generationConfig).toBeVisible()
  await expect(promptInput).toHaveCount(1)
  await expect(config.getByText('Prompt', { exact: true })).toHaveCount(0)
  await expect(
    config.getByText('Negative Prompt', { exact: true }),
  ).toHaveCount(0)
  const manualPrompt = '手机支架，纯色背景，突出金属质感。'
  await promptInput.fill(manualPrompt)
  await generationConfig
    .getByRole('navigation', { name: '输出格式' })
    .getByRole('button', { name: '四宫格' })
    .click()
  await chooseSelectOption(page, generationConfig.getByLabel('生成比例'), '3:4')
  const countInput = generationConfig.getByLabel('生成数量').locator('input')
  await countInput.fill('2')
  await countInput.press('Tab')

  const fileChooserPromise = page.waitForEvent('filechooser')
  await productSurface.click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({
    name: '临时商品图.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      'base64',
    ),
  })
  await expect(productSurface.getByAltText('临时商品图.png')).toBeVisible()
  await expect(productSlot.getByRole('button', { name: '上传' })).toHaveCount(0)

  await productSlot.getByRole('button', { name: '素材库', exact: true }).click()
  const assetDialog = page.getByRole('dialog')
  await expect(
    assetDialog.getByText('选择商品图片', { exact: true }),
  ).toBeVisible()
  await expect(
    assetDialog.getByRole('button', { name: '选择素材 正面.jpg' }),
  ).toBeVisible()
  await assetDialog.getByRole('button', { name: '选择素材 正面.jpg' }).click()
  await assetDialog.getByRole('button', { name: '选择', exact: true }).click()
  await expect(productSurface.getByAltText('正面.jpg')).toBeVisible()
  await expect(
    productSurface.locator('.generation-input-slot__image'),
  ).toHaveCount(2)
  const filledSlotBox = await productSurface.boundingBox()
  expect(Math.round(filledSlotBox?.width ?? 0)).toBe(
    Math.round(emptySlotBox?.width ?? 0),
  )
  expect(filledSlotBox?.height).toBeGreaterThanOrEqual(
    emptySlotBox?.height ?? 0,
  )
  await productSlot.getByRole('button', { name: '移除 临时商品图.png' }).click()
  await expect(productSurface.getByAltText('临时商品图.png')).toHaveCount(0)

  await config.getByRole('button', { name: '生成', exact: true }).click()
  const resultGrid = page.getByTestId('instant-result-grid')
  await expect(resultGrid).toBeVisible()
  await expect(resultGrid.getByTestId('instant-result-card')).toHaveCount(2)
  await expect(
    resultGrid.getByRole('button', { name: '下载' }).first(),
  ).toBeVisible()
  await expect(
    resultGrid.getByRole('button', { name: '保存到素材库' }).first(),
  ).toBeVisible()
  await resultGrid.getByRole('button', { name: '保存到素材库' }).first().click()
  const saveDialog = page.getByRole('dialog')
  await expect(saveDialog.getByLabel('目标产品素材组')).toContainText(
    '手机支架',
  )
  await saveDialog.getByRole('button', { name: '保存', exact: true }).click()

  await moduleNavigation.getByRole('button', { name: '生成记录' }).click()
  const recordRows = page.locator('.n-data-table-tbody .n-data-table-tr')
  await recordRows.first().getByRole('button', { name: '查看' }).click()
  const recordDrawer = page.getByRole('dialog')
  await expect(recordDrawer).toContainText(manualPrompt)
  await expect(recordDrawer).toContainText('未使用')
  await expect(recordDrawer).toContainText('四宫格 · 3:4 · 2 张')
  await expect(recordDrawer.getByText('提示词', { exact: true })).toBeVisible()
  await expect(recordDrawer.getByText('Prompt', { exact: true })).toHaveCount(0)
  await recordDrawer.getByRole('button', { name: '关闭' }).click()

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图' })
    .click()
  const restoredConfig = page.getByRole('region', { name: '即时生成配置' })
  await expect(restoredConfig.getByLabel('提示词')).toHaveValue(manualPrompt)
  await restoredConfig
    .getByRole('navigation', { name: '生成模式' })
    .getByRole('button', { name: '风格复刻' })
    .click()
  const styleSlots = restoredConfig.locator('[data-input-slot]')
  await expect(styleSlots).toHaveCount(2)
  const referenceSlot = restoredConfig.locator(
    '[data-input-slot="REFERENCE_IMAGES"]',
  )
  await expect(referenceSlot).toHaveAttribute('aria-label', '参考图片')
  const referenceSurfaceBox = await referenceSlot
    .locator('.generation-input-slot__surface')
    .boundingBox()
  expect(referenceSurfaceBox?.height).toBeGreaterThanOrEqual(160)
  await expect(
    restoredConfig
      .getByRole('navigation', { name: '生成模式' })
      .getByRole('button', { name: '风格复刻' }),
  ).toHaveAttribute('aria-pressed', 'true')
  const libraryButtons = restoredConfig.getByRole('button', {
    name: '素材库',
    exact: true,
  })
  await expect(libraryButtons).toHaveCount(2)
  await referenceSlot
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  const referenceDialog = page.getByRole('dialog')
  await expect(
    referenceDialog.getByRole('button', {
      name: '选择素材 参考-极简白底.jpg',
    }),
  ).toBeVisible()
  await expect(
    referenceDialog.getByRole('button', { name: '选择素材 正面.jpg' }),
  ).toHaveCount(0)
  await referenceDialog.getByRole('button', { name: '取消' }).click()

  const layout = await page.evaluate(() => ({
    documentHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    mainVerticalOverflow:
      document.querySelector('main')!.scrollHeight >
      document.querySelector('main')!.clientHeight,
    configScrollable:
      document.querySelector('.instant-generation-pane__scroll')!.scrollHeight >
      document.querySelector('.instant-generation-pane__scroll')!.clientHeight,
  }))
  expect(layout).toEqual({
    documentHorizontalOverflow: false,
    mainVerticalOverflow: false,
    configScrollable: true,
  })
  expect(runtimeErrors).toEqual([])
})

test('renders stable instant result slots with preview and isolated retry', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')

  const config = page.getByRole('region', { name: '即时生成配置' })
  const workspace = page.getByRole('region', { name: '即时生成结果' })
  const viewer = workspace.getByTestId('instant-result-viewer')
  await expect(viewer.getByText('暂无生成结果', { exact: true })).toBeVisible()

  await config.getByRole('button', { name: '素材库', exact: true }).click()
  const assetDialog = page.getByRole('dialog')
  await assetDialog.getByRole('button', { name: '选择素材 正面.jpg' }).click()
  await assetDialog.getByRole('button', { name: '选择', exact: true }).click()
  await config.getByLabel('提示词').fill('即时结果预览测试')
  const countInput = config.getByLabel('生成数量').locator('input')
  await countInput.fill('4')
  await countInput.press('Tab')
  await config.getByRole('button', { name: '生成', exact: true }).click()

  const summary = viewer.getByTestId('instant-execution-summary')
  const progress = viewer.getByTestId('instant-execution-progress')
  const cards = viewer.getByTestId('instant-result-card')
  await expect(cards).toHaveCount(4)
  await expect(summary).toHaveAttribute('data-execution-status', 'RUNNING')
  await expect(progress).toBeVisible()
  for (const status of ['SUCCESS', 'RUNNING', 'WAITING', 'FAILED']) {
    await expect(
      viewer.locator(
        `[data-testid="instant-result-card"][data-result-status="${status}"]`,
      ),
    ).toHaveCount(1)
  }

  const initialIds = await cards.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute('data-result-id')),
  )
  const initialSlots = await cards.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute('data-slot-index')),
  )
  expect(initialSlots).toEqual(['0', '1', '2', '3'])

  const successCard = viewer.locator(
    '[data-testid="instant-result-card"][data-result-status="SUCCESS"]',
  )
  await successCard.getByAltText('生成结果-01.webp').click()
  await expect(page.locator('.n-image-preview-container')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(
    successCard.getByRole('button', { name: /下载 生成结果-01/ }),
  ).toBeVisible()
  await expect(
    successCard.getByRole('button', { name: /保存到素材库 生成结果-01/ }),
  ).toBeVisible()
  await successCard
    .getByRole('button', { name: /保存到素材库 生成结果-01/ })
    .click()
  const saveDialog = page.getByRole('dialog')
  await expect(
    saveDialog.getByText('保存到素材库', { exact: true }),
  ).toBeVisible()
  await saveDialog.getByRole('button', { name: '取消' }).click()
  await expect(summary.getByRole('button', { name: '下载全部' })).toBeEnabled()

  await expect(summary).toHaveAttribute(
    'data-execution-status',
    'PARTIAL_FAILED',
    { timeout: 5000 },
  )
  const stats = summary.getByTestId('instant-execution-stats').locator('dd')
  await expect(stats.nth(0)).toHaveText('3')
  await expect(stats.nth(1)).toHaveText('0')
  await expect(stats.nth(2)).toHaveText('0')
  await expect(stats.nth(3)).toHaveText('1')

  const failedCard = viewer.locator(
    '[data-testid="instant-result-card"][data-result-status="FAILED"]',
  )
  const failedId = await failedCard.getAttribute('data-result-id')
  await failedCard.getByRole('button', { name: /重试 生成结果-04/ }).click()
  const retriedCard = viewer.locator(
    `[data-testid="instant-result-card"][data-result-id="${failedId}"]`,
  )
  await expect(retriedCard).toHaveAttribute('data-result-status', 'RUNNING')
  await expect(retriedCard).toHaveAttribute('data-result-status', 'SUCCESS', {
    timeout: 3000,
  })
  await expect(summary).toHaveAttribute('data-execution-status', 'SUCCESS')
  await expect(summary).toContainText('4 / 4')
  await expect(summary).toContainText('100.0%')
  await expect(stats.nth(0)).toHaveText('4')
  await expect(stats.nth(3)).toHaveText('0')

  const finalIds = await cards.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute('data-result-id')),
  )
  expect(finalIds).toEqual(initialIds)
  expect(finalIds.filter((id) => id === failedId)).toHaveLength(1)
  await expect(
    viewer.locator(
      '[data-testid="instant-result-card"][data-result-status="SUCCESS"]',
    ),
  ).toHaveCount(4)

  const scrollContract = await viewer.evaluate((element) => {
    const summaryElement = element.querySelector(
      '[data-testid="instant-execution-summary"]',
    )!
    const scrollElement = element.querySelector(
      '[data-testid="instant-result-scroll"]',
    )!
    return {
      sameParent: summaryElement.parentElement === scrollElement.parentElement,
      summaryInsideScroll: scrollElement.contains(summaryElement),
      resultOverflowY: getComputedStyle(scrollElement).overflowY,
    }
  })
  expect(scrollContract).toEqual({
    sameParent: true,
    summaryInsideScroll: false,
    resultOverflowY: 'auto',
  })

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(viewer).toBeVisible()
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(viewer).toBeVisible()

  const layout = await page.evaluate(() => ({
    horizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    documentVerticalOverflow:
      document.documentElement.scrollHeight >
      document.documentElement.clientHeight,
    mainVerticalOverflow:
      document.querySelector('main')!.scrollHeight >
      document.querySelector('main')!.clientHeight,
  }))
  expect(layout).toEqual({
    horizontalOverflow: false,
    documentVerticalOverflow: false,
    mainVerticalOverflow: false,
  })
  expect(runtimeErrors).toEqual([])
})

test('uses templates as editable fill sources and records the final config', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')

  const config = page.getByRole('region', { name: '即时生成配置' })
  await config.getByRole('button', { name: '素材库', exact: true }).click()
  const assetDialog = page.getByRole('dialog')
  await assetDialog.getByRole('button', { name: '选择素材 正面.jpg' }).click()
  await assetDialog.getByRole('button', { name: '选择', exact: true }).click()

  const templatePrompt =
    '{product_name}，极简白底主图，突出{selling_points}，避免模糊、变形、多余文字和低清晰度。'
  const templateSelect = config.getByLabel('生成模板')
  await chooseSelectOption(page, templateSelect, '极简白底')
  const editableConfig = config.getByTestId('instant-generation-config')
  const promptInput = editableConfig.getByLabel('提示词')
  const outputFormat = editableConfig.getByRole('navigation', {
    name: '输出格式',
  })
  const sizeSelect = editableConfig.getByLabel('生成比例')
  const countInput = editableConfig.getByLabel('生成数量').locator('input')
  await expect(templateSelect).toContainText('极简白底')
  await expect(promptInput).toHaveValue(templatePrompt)
  await expect(
    outputFormat.getByRole('button', { name: '单图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(sizeSelect).toContainText('1:1')
  await expect(countInput).toHaveValue('1')
  await expect(config.getByTestId('template-summary')).toHaveCount(0)

  await promptInput.fill('即将被下一模板覆盖')
  await chooseSelectOption(page, templateSelect, '核心卖点')
  await expect(templateSelect).toContainText('核心卖点')
  await expect(promptInput).not.toHaveValue('即将被下一模板覆盖')
  await expect(
    config
      .locator('[data-input-slot="PRODUCT_IMAGES"]')
      .getByAltText('正面.jpg'),
  ).toBeVisible()

  const clearedPrompt = await promptInput.inputValue()
  const clearedSize = await sizeSelect.textContent()
  const clearedCount = await countInput.inputValue()
  await templateSelect.locator('.n-base-clear').click({ force: true })
  await expect(templateSelect).not.toContainText('核心卖点')
  await expect(promptInput).toHaveValue(clearedPrompt)
  await expect(sizeSelect).toHaveText(clearedSize ?? '')
  await expect(countInput).toHaveValue(clearedCount)

  await chooseSelectOption(page, templateSelect, '极简白底')
  const finalPrompt = '最终生成：手机支架，暖灰背景，突出金属结构。'
  await promptInput.fill(finalPrompt)
  await outputFormat.getByRole('button', { name: '四宫格' }).click()
  await chooseSelectOption(page, sizeSelect, '3:4')
  await countInput.fill('2')
  await countInput.press('Tab')

  await config.getByRole('button', { name: '生成', exact: true }).click()
  await expect(
    page.getByTestId('instant-result-grid').getByTestId('instant-result-card'),
  ).toHaveCount(2)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  const firstRow = page.locator('.n-data-table-tbody .n-data-table-tr').first()
  await firstRow.getByRole('button', { name: '查看' }).click()
  const recordDrawer = page.getByRole('dialog')
  await expect(recordDrawer).toContainText('极简白底')
  await expect(recordDrawer).toContainText(finalPrompt)
  await expect(recordDrawer).toContainText('四宫格 · 3:4 · 2 张')
  await recordDrawer.getByRole('button', { name: '关闭' }).click()

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await page.getByRole('button', { name: '选择模板 极简白底' }).click()
  const editor = page.getByRole('region', { name: '模板编辑' })
  await expect(editor.getByLabel('提示词')).toHaveValue(templatePrompt)
  await expect(editor.getByText('Prompt', { exact: true })).toHaveCount(0)
  await expect(
    editor.getByText('Negative Prompt', { exact: true }),
  ).toHaveCount(0)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图' })
    .click()
  const restoredConfig = page.getByRole('region', { name: '即时生成配置' })
  await expect(restoredConfig.getByLabel('提示词')).toHaveValue(finalPrompt)
  await expect(restoredConfig.getByTestId('template-summary')).toHaveCount(0)
  await restoredConfig
    .getByRole('navigation', { name: '生成模式' })
    .getByRole('button', { name: '风格复刻' })
    .click()
  await expect(
    restoredConfig
      .getByRole('navigation', { name: '生成模式' })
      .getByRole('button', { name: '风格复刻' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(restoredConfig.getByLabel('生成模板')).not.toContainText(
    '极简白底',
  )
  await expect(restoredConfig.getByLabel('提示词')).toHaveValue(finalPrompt)
  expect(runtimeErrors).toEqual([])
})

test('completes batch configuration and the master-detail execution viewer', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')
  await page
    .getByRole('navigation', { name: '生成工作方式' })
    .getByRole('button', { name: '批量生成' })
    .click()

  const config = page.getByRole('region', { name: '批量生成配置' })
  const modeSwitch = config.getByRole('navigation', { name: '批量生成模式' })
  const productRange = config.getByRole('navigation', { name: '产品范围' })
  const templateSource = config.getByRole('navigation', { name: '模板来源' })
  const outputRange = config.getByRole('navigation', { name: '输出范围' })
  await expect(
    productRange.getByRole('button', { name: '所有已启用产品' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    templateSource.getByRole('button', { name: '产品已配置' }),
  ).toHaveAttribute('aria-pressed', 'true')
  for (const control of [
    modeSwitch,
    productRange,
    templateSource,
    outputRange,
  ]) {
    await expect(control).toHaveClass(/context-switch-bar/)
  }
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()

  const productList = config.getByTestId('batch-product-list')
  const productListLayout = await productList.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }))
  expect(productListLayout.clientHeight).toBeGreaterThan(190)
  expect(productListLayout.clientHeight).toBeLessThan(230)
  expect(productListLayout.scrollHeight).toBeGreaterThan(
    productListLayout.clientHeight,
  )

  await config.getByRole('button', { name: '执行检查' }).click()
  const preflight = page.getByTestId('batch-preflight')
  await expect(preflight).toContainText('产品')
  await expect(preflight).toContainText('可执行')
  await expect(preflight).toContainText('跳过')
  await expect(preflight).toContainText('模板组')
  await expect(preflight).toContainText('生成项')
  await page.getByRole('button', { name: '查看问题' }).click()
  const issueDialog = page.getByRole('dialog')
  await expect(issueDialog).toContainText('无商品素材')
  await expect(issueDialog).toContainText('模板组停用')
  await expect(issueDialog).toContainText('所有模板均停用')
  await issueDialog.getByRole('button', { name: '关闭' }).click()

  await outputRange.getByRole('button', { name: '仅主图' }).click()
  await config.getByRole('button', { name: '执行检查' }).click()
  await expect(preflight).toBeVisible()
  await outputRange.getByRole('button', { name: '仅详情' }).click()
  await config.getByRole('button', { name: '执行检查' }).click()
  await expect(preflight).toBeVisible()

  await templateSource.getByRole('button', { name: '本次选择' }).click()
  await chooseSelectOption(
    page,
    config.getByLabel('本次模板组'),
    '电商标准套图 A',
  )
  await page.keyboard.press('Escape')

  await productRange.getByRole('button', { name: '选择产品' }).click()
  const productDialog = page.getByRole('dialog')
  await productDialog.getByRole('button', { name: '选择产品 手机支架' }).click()
  await productDialog.getByRole('button', { name: '确定' }).click()
  await expect(productList.getByText('手机支架', { exact: true })).toBeVisible()

  const productField = config
    .locator('.batch-generation-field')
    .filter({ hasText: '产品范围' })
    .first()
  const templateField = config
    .locator('.batch-generation-field')
    .filter({ hasText: '模板来源' })
    .first()
  await productField.getByRole('button', { name: '清空' }).click()
  await expect(config.getByLabel('本次模板组')).toContainText('电商标准套图 A')

  await productRange.getByRole('button', { name: '选择产品' }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '选择产品 手机支架' })
    .click()
  await page.getByRole('dialog').getByRole('button', { name: '确定' }).click()
  await templateField.getByRole('button', { name: '清空' }).click()
  await expect(productList.getByText('手机支架', { exact: true })).toBeVisible()

  await chooseSelectOption(
    page,
    config.getByLabel('本次模板组'),
    '电商标准套图 A',
  )
  await page.keyboard.press('Escape')
  await productRange.getByRole('button', { name: '所有已启用产品' }).click()
  await templateSource.getByRole('button', { name: '产品已配置' }).click()
  await outputRange.getByRole('button', { name: '全部' }).click()
  await config.getByRole('button', { name: '执行检查' }).click()
  await config.getByRole('button', { name: '开始生成' }).click()

  const viewer = page.getByTestId('batch-execution-viewer')
  const summary = viewer.getByTestId('batch-execution-summary')
  const runtimeStats = viewer.getByTestId('batch-runtime-stats')
  const executionFilter = viewer.getByRole('navigation', {
    name: '执行结果筛选',
  })
  const productTasks = viewer.getByTestId('batch-product-task-list')
  const detail = viewer.getByTestId('batch-product-result-detail')
  await expect(viewer).toBeVisible()
  await expect(summary).toContainText('执行结果')
  await expect(viewer.getByTestId('batch-execution-progress')).toBeVisible()
  for (const label of ['成功', '生成中', '等待中', '失败']) {
    await expect(runtimeStats.getByText(label, { exact: true })).toBeVisible()
  }
  await expectBareSwitchBar(executionFilter)
  await expect(
    executionFilter.getByRole('button', { name: '全部' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(productTasks).toBeVisible()
  expect(
    await productTasks.getByTestId('batch-product-task-row').count(),
  ).toBeGreaterThan(10)

  const phoneRow = productTasks.locator('[data-product-id="pmg-phone-stand"]')
  const mugRow = productTasks.locator('[data-product-id="pmg-mug"]')
  await expect(phoneRow).toHaveAttribute('data-active', 'true')
  await expect(detail).toContainText('手机支架')
  await mugRow.getByRole('button', { name: '查看产品任务 马克杯' }).click()
  await expect(mugRow).toHaveAttribute('data-active', 'true')
  await expect(detail).toContainText('马克杯')
  await phoneRow.getByRole('button', { name: '查看产品任务 手机支架' }).click()

  const firstGroup = detail.locator(
    '[data-template-group-id="normal-standard-set"]',
  )
  await expect(firstGroup).toContainText('电商标准套图 A')
  await expect(firstGroup.getByText('极简白底', { exact: true })).toBeVisible()
  for (const status of [
    'SUCCESS',
    'RUNNING',
    'WAITING',
    'FAILED',
    'PARTIAL_FAILED',
  ]) {
    await expect(
      firstGroup.locator(`[data-template-status="${status}"]`).first(),
    ).toBeVisible()
  }
  for (const status of ['SUCCESS', 'RUNNING', 'WAITING', 'FAILED']) {
    await expect(
      firstGroup.locator(`[data-result-status="${status}"]`).first(),
    ).toBeVisible()
  }

  const successPreview = firstGroup
    .locator('[data-result-status="SUCCESS"] img')
    .first()
  await expect
    .poll(() =>
      successPreview.evaluate(
        (image) => (image as HTMLImageElement).naturalWidth,
      ),
    )
    .toBeGreaterThan(0)
  await successPreview.click()
  await expect(page.locator('.n-image-preview-container')).toBeVisible()
  await page.keyboard.press('Escape')

  const firstGroupHeader = firstGroup
    .locator('.n-collapse-item__header')
    .first()
  await firstGroupHeader.click()
  await expect(
    firstGroup.getByTestId('batch-template-execution-card').first(),
  ).toBeHidden()
  await firstGroupHeader.click()
  await expect(
    firstGroup.getByTestId('batch-template-execution-card').first(),
  ).toBeVisible()

  const failedTemplate = firstGroup
    .locator('[data-template-status="FAILED"]')
    .first()
  const failedTemplateId = await failedTemplate.getAttribute('data-template-id')
  await failedTemplate.getByRole('button', { name: /^重试 / }).click()
  await expect(
    firstGroup.locator(`[data-template-id="${failedTemplateId}"]`),
  ).toHaveAttribute('data-template-status', 'RUNNING')

  const allProductCount = await productTasks
    .getByTestId('batch-product-task-row')
    .count()
  await mugRow.getByRole('button', { name: '查看产品任务 马克杯' }).click()
  await executionFilter.getByRole('button', { name: '生成中' }).click()
  await expect(productTasks.locator('[data-product-id="pmg-mug"]')).toHaveCount(
    0,
  )
  await expect(
    productTasks.getByTestId('batch-product-task-row').first(),
  ).toHaveAttribute('data-active', 'true')
  const runningProductCount = await productTasks
    .getByTestId('batch-product-task-row')
    .count()
  expect(runningProductCount).toBeLessThan(allProductCount)
  await executionFilter.getByRole('button', { name: '失败' }).click()
  const failedProductRows = productTasks.getByTestId('batch-product-task-row')
  expect(await failedProductRows.count()).toBeGreaterThan(0)
  await expect(failedProductRows.first()).toHaveAttribute('data-active', 'true')
  await executionFilter.getByRole('button', { name: '全部' }).click()
  await expect(productTasks.getByTestId('batch-product-task-row')).toHaveCount(
    allProductCount,
  )

  await viewer.getByRole('button', { name: '查看问题' }).click()
  const problemDialog = page.getByRole('dialog')
  await expect(problemDialog).toContainText('跳过')
  await expect(problemDialog).toContainText('失败')
  await problemDialog.getByRole('button', { name: '关闭' }).click()
  await viewer.getByRole('button', { name: '下载全部' }).click()
  await expect(page.getByText('下载任务已创建', { exact: true })).toBeVisible()

  await phoneRow.getByRole('button', { name: '查看产品任务 手机支架' }).click()
  const summaryTopBeforeScroll = (await summary.boundingBox())!.y
  const scrollState = await page.evaluate(
    ({ productSelector, detailSelector }) => {
      const productList = document.querySelector<HTMLElement>(productSelector)!
      const detailList = document.querySelector<HTMLElement>(detailSelector)!
      productList.scrollTop = productList.scrollHeight
      detailList.scrollTop = detailList.scrollHeight
      return {
        productClientHeight: productList.clientHeight,
        productScrollHeight: productList.scrollHeight,
        productScrollTop: productList.scrollTop,
        detailClientHeight: detailList.clientHeight,
        detailScrollHeight: detailList.scrollHeight,
        detailScrollTop: detailList.scrollTop,
      }
    },
    {
      productSelector: '[data-testid="batch-product-task-list"]',
      detailSelector: '[data-testid="batch-product-detail-scroll"]',
    },
  )
  expect(scrollState.productScrollHeight).toBeGreaterThan(
    scrollState.productClientHeight,
  )
  expect(scrollState.productScrollTop).toBeGreaterThan(0)
  expect(scrollState.detailScrollHeight).toBeGreaterThan(
    scrollState.detailClientHeight,
  )
  expect(scrollState.detailScrollTop).toBeGreaterThan(0)
  expect((await summary.boundingBox())!.y).toBe(summaryTopBeforeScroll)

  const productListBox = (await viewer
    .getByRole('region', { name: '产品任务列表' })
    .boundingBox())!
  const detailBox = (await detail.boundingBox())!
  expect(productListBox.width).toBeGreaterThanOrEqual(260)
  expect(productListBox.width).toBeLessThanOrEqual(300)
  expect(detailBox.width).toBeGreaterThan(300)

  const overflow = await page.evaluate(() => {
    return {
      document: document.documentElement.scrollWidth > window.innerWidth,
      documentVertical:
        document.documentElement.scrollHeight >
        document.documentElement.clientHeight,
      mainVertical:
        document.querySelector('main')!.scrollHeight >
        document.querySelector('main')!.clientHeight,
      viewer:
        document.querySelector<HTMLElement>(
          '[data-testid="batch-execution-viewer"]',
        )!.scrollWidth >
        document.querySelector<HTMLElement>(
          '[data-testid="batch-execution-viewer"]',
        )!.clientWidth,
    }
  })
  expect(overflow).toEqual({
    document: false,
    documentVertical: false,
    mainVertical: false,
    viewer: false,
  })

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/records\?visualMock=1$/)
  const firstDataRow = page
    .locator('.n-data-table-tbody .n-data-table-tr')
    .first()
  await expect(firstDataRow).toContainText('批量生成')
  await expect(firstDataRow).toContainText('当前用户')
  expect(runtimeErrors).toEqual([])
})

test('filters, paginates and opens generation record details in both themes', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/records?visualMock=1')

  const rows = page.locator('.n-data-table-tbody .n-data-table-tr')
  await expect(rows).toHaveCount(20)
  const firstTime = await rows
    .nth(0)
    .locator('.n-data-table-td')
    .nth(0)
    .innerText()
  const secondTime = await rows
    .nth(1)
    .locator('.n-data-table-td')
    .nth(0)
    .innerText()
  expect(new Date(firstTime).getTime()).toBeGreaterThanOrEqual(
    new Date(secondTime).getTime(),
  )

  await chooseSelectOption(page, page.getByLabel('任务类型'), '即时生成')
  await expect(rows.first()).toContainText('即时生成')
  await expect(rows.filter({ hasText: '批量生成' })).toHaveCount(0)
  await rows.first().getByRole('button', { name: '查看' }).click()
  const instantDrawer = page.getByRole('dialog')
  await expect(instantDrawer).toContainText('即时生成')
  await expect(instantDrawer).toContainText('生成配置')
  await expect(instantDrawer.getByText('提示词', { exact: true })).toBeVisible()
  await expect(instantDrawer.getByText('Prompt', { exact: true })).toHaveCount(
    0,
  )
  await expect(
    instantDrawer.getByText('Negative Prompt', { exact: true }),
  ).toHaveCount(0)
  await expect(instantDrawer.getByTestId('instant-result-grid')).toBeVisible()
  await instantDrawer.getByRole('button', { name: '关闭' }).click()

  await chooseSelectOption(page, page.getByLabel('任务类型'), '全部类型')
  await chooseSelectOption(page, page.getByLabel('生成模式'), '风格复刻')
  await expect(rows.first()).toContainText('风格复刻')
  await chooseSelectOption(page, page.getByLabel('生成模式'), '全部模式')
  await chooseSelectOption(page, page.getByLabel('任务状态'), '部分失败')
  await expect(rows.first()).toContainText('部分失败')

  await rows.first().getByRole('button', { name: '查看' }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toContainText('创建人')
  await expect(drawer).toContainText('批量结果')
  await expect(drawer.getByTestId('batch-result-tree')).toBeVisible()
  await expect(
    drawer.getByTestId('batch-result-tree').locator('details'),
  ).not.toHaveCount(0)
  await expect(drawer.getByRole('button', { name: '重试失败项' })).toBeVisible()
  await drawer.getByRole('button', { name: '重试失败项' }).click()
  await expect(drawer).toContainText('成功')
  await expect(drawer.getByRole('button', { name: '重试失败项' })).toHaveCount(
    0,
  )
  await drawer.getByRole('button', { name: '关闭' }).click()

  await chooseSelectOption(page, page.getByLabel('任务状态'), '全部状态')
  const recordSearch = page.getByLabel('搜索生成记录')
  await recordSearch.fill('张三')
  await expect(rows.first()).toContainText('张三')
  await recordSearch.fill('')

  const pagination = page.locator('.generation-records-panel .pagination-bar')
  await expect(pagination).toContainText('共 25 条')
  const paginationLayout = await page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>(
      '.generation-records-panel',
    )!
    const paginationBar = panel.querySelector<HTMLElement>('.pagination-bar')!
    return {
      panelBottom: Math.round(panel.getBoundingClientRect().bottom),
      paginationBottom: Math.round(
        paginationBar.getBoundingClientRect().bottom,
      ),
      horizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      mainVerticalOverflow:
        document.querySelector('main')!.scrollHeight >
        document.querySelector('main')!.clientHeight,
    }
  })
  expect(
    paginationLayout.panelBottom - paginationLayout.paginationBottom,
  ).toBeLessThanOrEqual(20)
  expect(paginationLayout.horizontalOverflow).toBe(false)
  expect(paginationLayout.mainVerticalOverflow).toBe(false)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(pagination).toBeVisible()
  await rows.first().getByRole('button', { name: '查看' }).click()
  await expect(page.getByRole('dialog')).toContainText('任务信息')
  await page.getByRole('dialog').getByRole('button', { name: '关闭' }).click()
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  expect(runtimeErrors).toEqual([])
})

test('keeps every generation interaction stable in light and dark themes', async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page)
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate?visualMock=1')

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')

  const instantConfig = page.getByRole('region', { name: '即时生成配置' })
  await instantConfig
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  const assetDialog = page.getByRole('dialog')
  await expect(assetDialog).toBeVisible()
  await assetDialog.getByRole('button', { name: '选择素材 正面.jpg' }).click()
  await assetDialog.getByRole('button', { name: '选择', exact: true }).click()

  await chooseSelectOption(
    page,
    instantConfig.getByLabel('生成模板'),
    '极简白底',
  )
  await expect(instantConfig.getByTestId('template-summary')).toHaveCount(0)
  await expect(
    instantConfig.getByTestId('instant-generation-config'),
  ).toBeVisible()
  await instantConfig.getByRole('button', { name: '生成', exact: true }).click()
  await expect(page.getByTestId('instant-result-grid')).toBeVisible()

  await page
    .getByRole('navigation', { name: '生成工作方式' })
    .getByRole('button', { name: '批量生成' })
    .click()
  const batchConfig = page.getByRole('region', { name: '批量生成配置' })
  await batchConfig.getByRole('button', { name: '执行检查' }).click()
  await batchConfig.getByRole('button', { name: '开始生成' }).click()
  await expect(page.getByTestId('batch-execution-viewer')).toBeVisible()

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByTestId('batch-execution-viewer')).toBeVisible()

  await page
    .getByRole('navigation', { name: '生成工作方式' })
    .getByRole('button', { name: '即时生成' })
    .click()
  await expect(instantConfig.getByLabel('生成模板')).toContainText('极简白底')
  await expect(page.getByTestId('instant-result-grid')).toBeVisible()
  await instantConfig
    .getByLabel('生成模板')
    .locator('.n-base-clear')
    .click({ force: true })
  await expect(instantConfig.getByLabel('提示词')).toBeVisible()
  await instantConfig
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
  await expect(instantConfig.getByLabel('生成模板')).toBeVisible()

  const layout = await page.evaluate(() => ({
    documentHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    mainVerticalOverflow:
      document.querySelector('main')!.scrollHeight >
      document.querySelector('main')!.clientHeight,
  }))
  expect(layout).toEqual({
    documentHorizontalOverflow: false,
    mainVerticalOverflow: false,
  })
  expect(runtimeErrors).toEqual([])
})

test('keeps normal and non-exact generation routes free of fixtures', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()
  await expect(page.getByText('手机支架', { exact: true })).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '生成', exact: true }),
  ).toBeDisabled()

  await page.goto('/#/ai-workbench/records')
  await expect(page.getByText('暂无生成记录', { exact: true })).toBeVisible()
  await expect(page.getByText('张三', { exact: true })).toHaveCount(0)

  await page.goto('/#/ai-workbench/records?visualMock=true')
  await expect(page.getByText('暂无生成记录', { exact: true })).toBeVisible()
  await expect(page.getByText('张三', { exact: true })).toHaveCount(0)
})
