import { expect, test, type Locator, type Page } from '@playwright/test'

function visibleSelectMenu(page: Page): Locator {
  return page.locator('.n-base-select-menu:visible')
}

function visibleDropdownMenu(page: Page): Locator {
  return page.locator('.n-dropdown-menu:visible').last()
}

async function chooseSelectOption(
  page: Page,
  control: Locator,
  label: string,
): Promise<void> {
  await control.click()
  await visibleSelectMenu(page).getByText(label, { exact: true }).click()
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

test('completes the template library V1 visual interactions', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/templates?visualMock=1')

  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(
    moduleNavigation.getByRole('button', { name: '模板库' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.ai-module-shell h1')).toHaveCount(0)
  await expect(page.locator('.ai-module-shell .page-header')).toHaveCount(0)

  const toolbar = page.getByRole('region', { name: '模板库工具栏' })
  const modeSelect = toolbar.getByLabel('生成模式')
  await expect(modeSelect).toContainText('普通生图')

  const workbench = page.locator('.three-pane-workbench')
  await expect(workbench).toBeVisible()
  await expect(workbench.locator('.three-pane-workbench__pane')).toHaveCount(3)

  const groupList = page.getByRole('region', { name: '模板组列表' })
  const groupRows = groupList.locator('.compact-entity-row')
  await expect(groupRows).toHaveCount(4)
  await expect(groupList.locator('svg.lucide-folder')).toHaveCount(4)
  await expect(
    groupList.getByRole('button', { name: '选择模板组 电商标准套图 A' }),
  ).toHaveAttribute('aria-pressed', 'true')
  expect(
    await groupRows.evaluateAll((rows) =>
      rows.every((row) => row.getBoundingClientRect().height === 51),
    ),
  ).toBe(true)

  const sequence = page.getByRole('region', { name: '模板序列' })
  const sequenceRows = sequence.locator('.template-sequence-row')
  const mainRows = sequence.locator(
    '.template-sequence-row[data-output-role="MAIN_IMAGE"]',
  )
  const detailRows = sequence.locator(
    '.template-sequence-row[data-output-role="DETAIL_IMAGE"]',
  )
  const sequenceHeader = sequence.locator('.template-sequence-list__header')
  const roleFilters = sequenceHeader.getByRole('group', {
    name: '模板角色筛选',
  })
  const allFilter = roleFilters.locator('[data-role-filter="ALL"]')
  const mainFilter = roleFilters.locator('[data-role-filter="MAIN_IMAGE"]')
  const detailFilter = roleFilters.locator('[data-role-filter="DETAIL_IMAGE"]')
  const pagination = sequence.locator('.pagination-bar')
  await expect(sequenceRows).toHaveCount(20)
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)
  await expect(allFilter).toHaveText('全部 24')
  await expect(mainFilter).toHaveText('主图 12')
  await expect(detailFilter).toHaveText('详情 12')
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(mainRows).toHaveCount(12)
  await expect(detailRows).toHaveCount(8)
  await expect(sequenceRows.first()).toContainText('极简白底')
  await expect(
    sequenceRows.first().locator('.template-sequence-row__role'),
  ).toHaveText('主图')
  await expect(
    detailRows.first().locator('.template-sequence-row__role'),
  ).toHaveText('详情')
  await expect(sequenceRows.first()).toHaveAttribute('data-sort-order', '1')

  const headerLayout = await sequenceHeader.evaluate((header) => {
    const title = header.querySelector<HTMLElement>(
      '.template-sequence-list__title',
    )!
    const titleText = title.querySelector<HTMLElement>('strong')!
    const filters = header.querySelector<HTMLElement>('.template-role-filter')!
    const add = header.querySelector<HTMLElement>('[aria-label="添加模板"]')!
    const headerRect = header.getBoundingClientRect()
    const titleRect = title.getBoundingClientRect()
    const filtersRect = filters.getBoundingClientRect()
    const addRect = add.getBoundingClientRect()
    return {
      titleLeft: titleRect.left,
      titleRight: titleRect.right,
      filtersLeft: filtersRect.left,
      filtersRight: filtersRect.right,
      addLeft: addRect.left,
      addRight: addRect.right,
      headerRight: headerRect.right,
      titleTruncated: titleText.scrollWidth > titleText.clientWidth + 1,
      horizontalOverflow: header.scrollWidth > header.clientWidth + 1,
    }
  })
  expect(headerLayout.titleLeft).toBeLessThan(headerLayout.filtersLeft)
  expect(headerLayout.titleRight).toBeLessThanOrEqual(headerLayout.filtersLeft)
  expect(headerLayout.filtersRight).toBeLessThanOrEqual(headerLayout.addLeft)
  expect(headerLayout.addRight).toBeLessThanOrEqual(
    headerLayout.headerRight + 1,
  )
  expect(headerLayout.titleTruncated).toBe(false)
  expect(headerLayout.horizontalOverflow).toBe(false)

  await mainFilter.click()
  await expect(mainFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(pagination).toContainText('共 12 条')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(sequenceRows).toHaveCount(12)
  await expect(mainRows).toHaveCount(12)
  await expect(detailRows).toHaveCount(0)

  await detailFilter.click()
  await expect(detailFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(pagination).toContainText('共 12 条')
  await expect(sequenceRows).toHaveCount(12)
  await expect(mainRows).toHaveCount(0)
  await expect(detailRows).toHaveCount(12)

  await allFilter.click()
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(pagination).toContainText('共 24 条')
  await expect(sequenceRows).toHaveCount(20)
  await expect(mainRows).toHaveCount(12)
  await expect(detailRows).toHaveCount(8)

  await page.getByRole('button', { name: '选择模板 极简白底' }).click()
  const editor = page.getByRole('region', { name: '模板编辑' })
  await expect(editor).toBeVisible()
  await expect(editor.getByLabel('输出类型')).toHaveCount(0)
  await expect(editor.getByText('输出类型', { exact: true })).toHaveCount(0)
  await expect(editor.getByText('Prompt', { exact: true })).toHaveCount(0)
  await expect(
    editor.getByText('Negative Prompt', { exact: true }),
  ).toHaveCount(0)
  await expect(editor.getByLabel('提示词', { exact: true })).toHaveCount(1)
  await editor
    .getByLabel('提示词', { exact: true })
    .fill('更新后的视觉测试提示词')
  await chooseSelectOption(page, editor.getByLabel('比例'), '16:9')
  await editor.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('已保存', { exact: true })).toBeVisible()
  await expect(
    mainRows.getByRole('button', { name: '选择模板 极简白底' }),
  ).toBeVisible()
  await expect(sequenceRows.first()).toContainText('16:9')

  await sequenceHeader.getByRole('button', { name: '添加模板' }).click()
  await visibleDropdownMenu(page).getByText('主图', { exact: true }).click()
  const templateNameInput = editor.getByLabel('模板名称')
  await expect(templateNameInput).toHaveValue('新建模板')
  await expect(editor.getByLabel('比例')).toContainText('1:1')
  await templateNameInput.fill('视觉主图模板')
  await editor
    .getByLabel('提示词', { exact: true })
    .fill('{product_name} 视觉测试')
  await editor.getByRole('button', { name: '保存' }).click()
  await expect(sequence.locator('.pagination-bar')).toContainText('共 25 条')
  await expect(allFilter).toHaveText('全部 25')
  await expect(mainFilter).toHaveText('主图 13')
  await expect(detailFilter).toHaveText('详情 12')
  await expect(sequenceRows).toHaveCount(20)
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)
  await expect(
    mainRows.getByRole('button', { name: '选择模板 视觉主图模板' }),
  ).toBeVisible()
  await expect(mainRows.filter({ hasText: '视觉主图模板' })).toContainText(
    '1:1',
  )

  await sequenceHeader.getByRole('button', { name: '添加模板' }).click()
  await visibleDropdownMenu(page).getByText('详情', { exact: true }).click()
  await expect(editor.getByLabel('比例')).toContainText('3:4')
  await templateNameInput.fill('视觉详情模板')
  await chooseSelectOption(page, editor.getByLabel('比例'), '1:1')
  await editor.getByRole('button', { name: '保存' }).click()
  await expect(sequence.locator('.pagination-bar')).toContainText('共 26 条')
  await expect(allFilter).toHaveText('全部 26')
  await expect(mainFilter).toHaveText('主图 13')
  await expect(detailFilter).toHaveText('详情 13')
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)
  const createdDetail = detailRows.filter({ hasText: '视觉详情模板' })
  await expect(createdDetail).toBeVisible()
  await expect(
    createdDetail.locator('.template-sequence-row__role'),
  ).toHaveText('详情')
  await expect(createdDetail).toContainText('1:1')

  await selectPage(pagination, 1)
  await page.getByRole('button', { name: '视觉主图模板操作' }).click()
  await visibleDropdownMenu(page).getByText('复制模板', { exact: true }).click()
  const mainCopy = mainRows.filter({ hasText: '视觉主图模板 副本' })
  await expect(mainCopy).toHaveAttribute('data-output-role', 'MAIN_IMAGE')
  await expect(mainCopy.locator('.template-sequence-row__role')).toHaveText(
    '主图',
  )
  await expect(mainCopy).toContainText('1:1')
  await expect(sequence.locator('.pagination-bar')).toContainText('共 27 条')
  await expect(allFilter).toHaveText('全部 27')
  await expect(mainFilter).toHaveText('主图 14')
  await expect(detailFilter).toHaveText('详情 13')

  await page.getByRole('button', { name: '视觉主图模板 副本操作' }).click()
  await visibleDropdownMenu(page).getByText('删除', { exact: true }).click()
  const deleteTemplateDialog = page
    .getByRole('dialog')
    .filter({ hasText: '删除模板' })
  await expect(deleteTemplateDialog).toContainText(
    '确认删除模板“视觉主图模板 副本”？',
  )
  await deleteTemplateDialog.getByRole('button', { name: '删除' }).click()
  await expect(sequence.locator('.pagination-bar')).toContainText('共 26 条')
  await expect(allFilter).toHaveText('全部 26')
  await expect(mainFilter).toHaveText('主图 13')
  await expect(detailFilter).toHaveText('详情 13')

  await page.getByRole('button', { name: '极简白底操作' }).click()
  await visibleDropdownMenu(page).getByText('下移', { exact: true }).click()
  await expect(mainRows.nth(0)).toContainText('场景展示')
  await expect(sequenceRows.nth(0)).toHaveAttribute('data-sort-order', '1')
  await expect(mainRows.nth(1)).toContainText('极简白底')
  await expect(sequenceRows.nth(1)).toHaveAttribute('data-sort-order', '2')

  await page.getByRole('button', { name: '极简白底操作' }).click()
  await visibleDropdownMenu(page).getByText('上移', { exact: true }).click()
  await expect(mainRows.nth(0)).toContainText('极简白底')

  const lastMainRow = mainRows.last()
  await lastMainRow.getByRole('button', { name: /操作$/ }).click()
  await expect(
    visibleDropdownMenu(page)
      .locator('.n-dropdown-option')
      .filter({ hasText: '下移' })
      .locator('.n-dropdown-option-body'),
  ).toHaveClass(/n-dropdown-option-body--disabled/)
  await page.keyboard.press('Escape')

  const mainCount = await mainRows.count()
  await expect(detailRows.first()).toHaveAttribute(
    'data-sort-order',
    String(mainCount + 1),
  )

  await detailFilter.click()
  await expect(detailFilter).toHaveAttribute('aria-pressed', 'true')
  await toolbar.getByRole('button', { name: '新建模板组' }).click()
  const createGroupDialog = page
    .getByRole('dialog')
    .filter({ hasText: '新建模板组' })
  await createGroupDialog
    .getByPlaceholder('请输入模板组名称')
    .fill('视觉测试模板组')
  await expect(createGroupDialog.getByLabel('生成模式')).toContainText(
    '普通生图',
  )
  await createGroupDialog.getByRole('button', { name: '创建' }).click()
  await expect(
    groupList.getByRole('button', { name: '选择模板组 视觉测试模板组' }),
  ).toHaveAttribute('aria-pressed', 'true')
  const settings = page.getByRole('region', { name: '模板组设置' })
  await expect(settings).toContainText('普通生图')
  await expect(settings).toContainText('模板数量')
  await expect(settings).toContainText('0')
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(allFilter).toHaveText('全部 0')
  await expect(mainFilter).toHaveText('主图 0')
  await expect(detailFilter).toHaveText('详情 0')

  await page.getByRole('button', { name: '视觉测试模板组操作' }).click()
  await visibleDropdownMenu(page).getByText('删除', { exact: true }).click()
  const deleteGroupDialog = page
    .getByRole('dialog')
    .filter({ hasText: '删除模板组' })
  await deleteGroupDialog.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('视觉测试模板组', { exact: true })).toHaveCount(0)
  await expect(
    groupList.getByRole('button', { name: '选择模板组 新品详情套图' }),
  ).toHaveAttribute('aria-pressed', 'true')

  await detailFilter.click()
  await expect(detailFilter).toHaveAttribute('aria-pressed', 'true')
  await chooseSelectOption(page, modeSelect, '风格复刻')
  await expect(modeSelect).toContainText('风格复刻')
  await expect(
    groupList.getByRole('button', { name: '选择模板组 竞品复刻 A' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('电商标准套图 A', { exact: true })).toHaveCount(0)
  await expect(sequenceRows).toHaveCount(2)
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(allFilter).toHaveText('全部 2')
  await expect(mainFilter).toHaveText('主图 1')
  await expect(detailFilter).toHaveText('详情 1')
  await expect(mainRows).toHaveCount(1)
  await expect(detailRows).toHaveCount(1)
  await expect(sequenceRows.first()).toContainText('竞品主图复刻')

  await toolbar.getByLabel('搜索模板').fill('竞品详情复刻')
  await expect(sequenceRows).toHaveCount(1)
  await expect(sequenceRows.first()).toContainText('竞品详情复刻')
  await expect(
    sequenceRows.first().locator('.template-sequence-row__role'),
  ).toHaveText('详情')
  await expect(allFilter).toHaveText('全部 2')
  await expect(mainFilter).toHaveText('主图 1')
  await expect(detailFilter).toHaveText('详情 1')
  await expect(pagination).toContainText('共 1 条')

  await mainFilter.click()
  await expect(mainFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(sequenceRows).toHaveCount(0)
  await expect(pagination).toContainText('共 0 条')

  await detailFilter.click()
  await expect(detailFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(sequenceRows).toHaveCount(1)
  await expect(sequenceRows.first()).toContainText('竞品详情复刻')
  await expect(pagination).toContainText('共 1 条')

  await allFilter.click()
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(sequenceRows).toHaveCount(1)
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)

  expect(runtimeErrors).toEqual([])
})

test('keeps standard pagination fixed and the three-pane layout bounded', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/templates?visualMock=1')

  const sequence = page.getByRole('region', { name: '模板序列' })
  const pagination = sequence.locator('.pagination-bar')
  const sequenceHeader = sequence.locator('.template-sequence-list__header')
  const roleFilters = sequenceHeader.getByRole('group', {
    name: '模板角色筛选',
  })
  const allFilter = roleFilters.locator('[data-role-filter="ALL"]')
  const mainFilter = roleFilters.locator('[data-role-filter="MAIN_IMAGE"]')
  const detailFilter = roleFilters.locator('[data-role-filter="DETAIL_IMAGE"]')
  await expect(pagination).toContainText('共 24 条')
  await expect(pagination).toContainText('20 / 页')
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(allFilter).toHaveText('全部 24')
  await expect(mainFilter).toHaveText('主图 12')
  await expect(detailFilter).toHaveText('详情 12')
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)

  await sequenceHeader.getByRole('button', { name: '添加模板' }).click()
  await visibleDropdownMenu(page).getByText('主图', { exact: true }).click()
  await expect(pagination).toContainText('共 25 条')
  await expect(allFilter).toHaveText('全部 25')
  await expect(mainFilter).toHaveText('主图 13')
  await expect(detailFilter).toHaveText('详情 12')
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(20)
  await selectPage(pagination, 2)
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(5)
  await expect(
    sequence.locator('.template-sequence-row[data-output-role="DETAIL_IMAGE"]'),
  ).toHaveCount(5)
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)
  await selectPage(pagination, 1)

  const pageSizePicker = pagination.locator('.n-select')
  await pageSizePicker.click()
  for (const size of [10, 20, 50, 100]) {
    await expect(
      visibleSelectMenu(page).getByText(`${size} / 页`, { exact: true }),
    ).toBeVisible()
  }
  await visibleSelectMenu(page).getByText('10 / 页', { exact: true }).click()
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(10)
  await selectPage(pagination, 2)
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(10)
  await expect(
    sequence.locator('.template-sequence-row[data-output-role="MAIN_IMAGE"]'),
  ).toHaveCount(3)
  await expect(
    sequence.locator('.template-sequence-row[data-output-role="DETAIL_IMAGE"]'),
  ).toHaveCount(7)
  await expect(allFilter).toHaveText('全部 25')
  await expect(mainFilter).toHaveText('主图 13')
  await expect(detailFilter).toHaveText('详情 12')
  await expect(sequence.locator('.template-sequence-section')).toHaveCount(0)

  await detailFilter.click()
  await expect(detailFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(pagination).toContainText('共 12 条')
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(10)
  await expect(
    sequence.locator('.template-sequence-row[data-output-role="DETAIL_IMAGE"]'),
  ).toHaveCount(10)
  await selectPage(pagination, 2)
  await expect(sequence.locator('.template-sequence-row')).toHaveCount(2)
  await expect(
    sequence.locator('.template-sequence-row[data-output-role="DETAIL_IMAGE"]'),
  ).toHaveCount(2)

  await allFilter.click()
  await expect(allFilter).toHaveAttribute('aria-pressed', 'true')
  await expect(pagination.locator('.n-pagination-item--active')).toHaveText('1')
  await expect(pagination).toContainText('共 25 条')
  await selectPage(pagination, 2)

  const paginationTopBefore = await pagination.evaluate(
    (element) => element.getBoundingClientRect().top,
  )
  await sequence
    .locator('.template-sequence-list__scroll')
    .evaluate((element) => {
      element.scrollTop = element.scrollHeight
    })
  expect(
    await pagination.evaluate((element) => element.getBoundingClientRect().top),
  ).toBe(paginationTopBefore)

  await page.getByRole('button', { name: '选择模板 场景扩展 04' }).click()
  const layout = await page.evaluate(() => {
    const panes = Array.from(
      document.querySelectorAll<HTMLElement>('.three-pane-workbench__pane'),
    ).map((pane) => pane.getBoundingClientRect())
    const appContent = document.querySelector<HTMLElement>(
      '.app-shell__content',
    )!
    const listScroll = document.querySelector<HTMLElement>(
      '.template-sequence-list__scroll',
    )!
    const rightPane = document.querySelector<HTMLElement>(
      '.three-pane-workbench__pane--right',
    )!
    const saveFooter = document.querySelector<HTMLElement>(
      '.template-editor__footer',
    )!
    const rightRect = rightPane.getBoundingClientRect()
    const footerRect = saveFooter.getBoundingClientRect()

    return {
      bodyOverflow: getComputedStyle(document.body).overflow,
      documentHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
      appContentActuallyScrolls:
        appContent.scrollHeight > appContent.clientHeight + 1,
      workbenchHorizontalOverflow: (() => {
        const workbench = document.querySelector<HTMLElement>(
          '.three-pane-workbench',
        )!
        return workbench.scrollWidth > workbench.clientWidth + 1
      })(),
      paneWidths: panes.map((pane) => pane.width),
      paneLefts: panes.map((pane) => pane.left),
      listActuallyScrolls:
        listScroll.scrollHeight > listScroll.clientHeight + 1,
      rightActuallyScrolls: rightPane.scrollHeight > rightPane.clientHeight + 1,
      footerInsideRightPane:
        footerRect.bottom <= rightRect.bottom + 1 &&
        footerRect.top >= rightRect.top - 1,
    }
  })
  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.documentHorizontalOverflow).toBe(false)
  expect(layout.bodyHorizontalOverflow).toBe(false)
  expect(layout.appContentActuallyScrolls).toBe(false)
  expect(layout.workbenchHorizontalOverflow).toBe(false)
  expect(layout.paneWidths.every((width) => width >= 200)).toBe(true)
  expect(layout.paneLefts[0]).toBeLessThan(layout.paneLefts[1]!)
  expect(layout.paneLefts[1]).toBeLessThan(layout.paneLefts[2]!)
  expect(layout.listActuallyScrolls).toBe(true)
  expect(layout.rightActuallyScrolls).toBe(true)
  expect(layout.footerInsideRightPane).toBe(true)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('region', { name: '模板编辑' })).toBeVisible()

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByRole('region', { name: '模板编辑' })).toBeVisible()

  expect(runtimeErrors).toEqual([])
})

test('keeps normal and non-exact visual mock routes fixture-free', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/templates')
  await expect(page.getByText('暂无模板', { exact: true })).toBeVisible()
  await expect(page.getByText('电商标准套图 A', { exact: true })).toHaveCount(0)
  await expect(page.getByText('极简白底', { exact: true })).toHaveCount(0)
  await page.getByLabel('生成模式').click()
  await expect(visibleSelectMenu(page)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '新建模板组' })).toBeDisabled()

  await page.goto('/#/ai-workbench/templates?visualMock=true')
  await expect(page.getByText('暂无模板', { exact: true })).toBeVisible()
  await expect(page.getByText('电商标准套图 A', { exact: true })).toHaveCount(0)
})
