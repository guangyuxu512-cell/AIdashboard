import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-08-24T12:00:00+08:00'))
  await page.route(
    /\/api\/v1\/automation-app-configs\/yingdao\//,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: 'null',
      })
    },
  )
})

test('registers Schedule Center under Automation and renders the compact list', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/shops')
  await expect(page.getByText('自动化中心', { exact: true })).toBeVisible()
  await page.getByText('自动化中心', { exact: true }).click()
  await page.getByText('定时计划', { exact: true }).click()

  await expect(page).toHaveURL(/#\/schedules$/)
  await expect(page.getByRole('heading', { name: '定时计划' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
  for (const column of [
    '计划名称',
    '执行对象',
    '设备',
    '触发规则',
    '下次执行',
    '最近执行',
    '开启',
    '操作',
  ]) {
    await expect(page.getByRole('columnheader', { name: column })).toBeVisible()
  }
  await expect(page.getByText('每日商品发布（Fixture）')).toBeVisible()
  await expect(page.getByText('每天 09:30')).toBeVisible()
  await expect(page.getByText('共 2 条', { exact: true })).toBeVisible()
  expect(runtimeErrors).toEqual([])
})

test('filters schedules and preserves normal empty state', async ({ page }) => {
  await page.goto('/#/schedules')
  const toolbar = page.getByRole('region', { name: '筛选条件' })

  await toolbar.getByPlaceholder('搜索计划名称或执行对象').fill('库存同步')
  await expect(page.getByText('库存同步（Fixture）').first()).toBeVisible()
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()

  await toolbar.getByPlaceholder('搜索计划名称或执行对象').fill('不存在')
  await expect(page.getByText('暂无定时计划')).toBeVisible()
  await expect(page.getByText('加载失败')).toHaveCount(0)
})

test('keeps the selected-date control compact and aligned while the filter bar wraps', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/schedules')
  const toolbar = page.getByRole('region', { name: '筛选条件' })

  await toolbar.getByText('指定日期', { exact: true }).click()
  const datePicker = toolbar.locator('.n-date-picker')
  await expect(datePicker).toBeVisible()

  const desktopBounds = await Promise.all(
    [
      toolbar.locator('.n-radio-group'),
      datePicker,
      toolbar.locator('.n-input').last(),
    ].map((locator) => locator.boundingBox()),
  )
  expect(desktopBounds.every((bounds) => bounds !== null)).toBe(true)
  expect(desktopBounds.map((bounds) => Math.round(bounds!.height))).toEqual([
    34, 34, 34,
  ])
  const desktopCenters = desktopBounds.map(
    (bounds) => bounds!.y + bounds!.height / 2,
  )
  expect(Math.max(...desktopCenters) - Math.min(...desktopCenters)).toBeLessThanOrEqual(1)

  await page.setViewportSize({ width: 1024, height: 768 })
  await expect(datePicker).toBeVisible()
  const compactBounds = await datePicker.boundingBox()
  expect(Math.round(compactBounds!.height)).toBe(34)
  const dateFieldHeight = await datePicker.evaluate(
    (element) => element.parentElement?.getBoundingClientRect().height ?? 0,
  )
  expect(Math.round(dateFieldHeight)).toBe(34)
})

test('opens create form with real Device Inventory semantics and saves a mock plan', async ({
  page,
}) => {
  await page.goto('/#/schedules')
  await page.getByRole('button', { name: '+ 新建计划' }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: '新建定时计划' })

  await dialog.getByPlaceholder('例如 每日商品发布').fill('每日测试计划')
  await dialog.locator('.n-base-selection').nth(0).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '杭州-运营机-01' })
    .click()
  await expect(
    dialog.getByRole('checkbox', { name: '星河服饰旗舰店' }),
  ).toBeChecked()
  await dialog.locator('.n-base-selection').nth(2).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '商品发布（Fixture）' })
    .first()
    .click()
  await expect(
    dialog
      .locator('.n-base-selection-input__content')
      .filter({ hasText: '影刀应用' })
      .first(),
  ).toBeVisible()
  await expect(
    dialog.getByRole('radio', { name: '每天' }),
  ).toBeChecked()
  await dialog.getByRole('button', { name: '保存' }).click()

  await expect(page.getByText('每日测试计划')).toBeVisible()
  await expect(page.getByText('共 3 条', { exact: true })).toBeVisible()
})

test('shows schedule detail, history and reuses TaskRuntimeDrawer', async ({
  page,
}) => {
  await page.goto('/#/schedules')
  const row = page
    .getByRole('row')
    .filter({ hasText: '每日商品发布（Fixture）' })
  await row.getByRole('button', { name: '查看' }).click()
  const detail = page
    .getByRole('dialog')
    .filter({ hasText: '每日商品发布（Fixture）' })

  await expect(detail.getByText('中国标准时间（上海）')).toBeVisible()
  await expect(detail.getByText('成功', { exact: true })).toBeVisible()
  await expect(detail.getByText('app-fixture-product-publish-1')).toBeVisible()
  await expect(detail.getByText('yingdao.app.run')).toBeVisible()
  await detail.getByRole('button', { name: '运行详情' }).click()
  const runtime = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(runtime.getByText('系统回声验证')).toBeVisible()
})

test('shows a normal empty state when the selected device has no Business Skill', async ({
  page,
}) => {
  await page.goto('/#/schedules')
  await page.getByRole('button', { name: '+ 新建计划' }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: '新建定时计划' })

  await dialog.locator('.n-base-selection').nth(0).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '杭州-运营机-01' })
    .click()
  await expect(
    dialog.getByRole('checkbox', { name: '星河服饰旗舰店' }),
  ).toBeChecked()
  await dialog.locator('.n-base-selection').nth(1).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '业务 Skill' })
    .click()

  await expect(
    dialog.getByText('暂无业务 Skill。当前 Worker 尚未安装业务 Skill。'),
  ).toBeVisible()
  await expect(dialog.getByText('加载失败')).toHaveCount(0)
})

test('keeps the timezone menu inside a 1366×768 viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/schedules')
  await page.getByRole('button', { name: '+ 新建计划' }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: '新建定时计划' })
  const timezoneField = dialog.locator('.n-form-item').filter({ hasText: '时区' })

  await timezoneField.locator('.n-base-selection').click()
  const menu = page.locator('.app-select-menu--viewport-safe').last()
  await expect(menu).toBeVisible()

  const bounds = await menu.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.y).toBeGreaterThanOrEqual(0)
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(768)
  const scrollState = await menu.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }))
  expect(scrollState.clientHeight).toBeLessThanOrEqual(280)
  expect(scrollState.scrollHeight).toBeGreaterThanOrEqual(
    scrollState.clientHeight,
  )
  await expect(page.getByText('美国东部时间（纽约）')).toBeAttached()
})

test('edits, disables, enables and archives a schedule without changing page pattern', async ({
  page,
}) => {
  await page.goto('/#/schedules')
  const row = page
    .getByRole('row')
    .filter({ hasText: '每日商品发布（Fixture）' })
  const enabledSwitch = row.getByRole('switch')

  await expect(enabledSwitch).toBeChecked()
  await enabledSwitch.click()
  await expect(enabledSwitch).not.toBeChecked()
  await enabledSwitch.click()
  await expect(enabledSwitch).toBeChecked()

  await row.getByRole('button', { name: '查看' }).click()
  const detailDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('button', { name: '编辑' }),
  })
  await detailDrawer.getByRole('button', { name: '编辑' }).click()
  const editDialog = page
    .getByRole('dialog')
    .filter({ hasText: '编辑定时计划' })
  await editDialog
    .getByPlaceholder('例如 每日商品发布')
    .fill('每日商品发布（已编辑）')
  await editDialog.getByRole('button', { name: '保存' }).click()
  await expect(detailDrawer.getByText('每日商品发布（已编辑）')).toBeVisible()
  await detailDrawer.getByRole('button', { name: '移除计划' }).click()
  const removeDialog = page
    .getByRole('dialog')
    .filter({ hasText: '确认移除定时计划' })
  await removeDialog.getByRole('button', { name: '确认移除' }).click()

  await expect(page.getByText('每日商品发布（已编辑）')).toHaveCount(0)
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps Schedule Center inside ${viewport.width}×${viewport.height} in Light and Dark`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/schedules')
    await expect(page.getByText('每日商品发布（Fixture）')).toBeVisible()

    for (const theme of ['石墨浅色', '午夜青']) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page.locator('.n-dropdown').getByText(theme, { exact: true }).click()
      const overflow = await page.evaluate(() => ({
        document:
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
        body: document.body.scrollWidth > document.body.clientWidth,
      }))
      expect(overflow).toEqual({ document: false, body: false })
    }
  })
}
