import { expect, test, type Locator, type Page } from '@playwright/test'

interface AutomationFieldFixture {
  name: string
  label: string
  type: 'text'
  required: boolean
  default_value: string
  options: string[]
}

function automationFields(count: number): AutomationFieldFixture[] {
  return Array.from({ length: count }, (_, index) => ({
    name: `parameter_${index + 1}`,
    label: `参数 ${index + 1}`,
    type: 'text',
    required: false,
    default_value: '',
    options: [],
  }))
}

async function mockAutomationConfig(page: Page, initialCount: number) {
  let fields = automationFields(initialCount)
  let savedFields: unknown[] | null = null
  let version = 1
  await page.route(/\/api\/v1\/automation-app-configs\/yingdao\//, async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON() as {
        input_schema: { fields: AutomationFieldFixture[] }
      }
      fields = body.input_schema.fields
      savedFields = fields
      version += 1
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        config_id: '00000000-0000-4000-8000-000000000001',
        provider_code: 'yingdao',
        app_id: 'app-fixture-product-publish',
        schema_source: 'manual',
        input_schema: { fields },
        default_values: {},
        version,
        created_at: '2026-08-23T00:00:00Z',
        updated_at: '2026-08-23T00:00:00Z',
      }),
    })
  })
  return {
    savedFields: () => savedFields,
  }
}

async function openAutomationConfig(page: Page) {
  await page.goto('/#/devices')
  await page.getByRole('button', { name: '查看' }).first().click()
  const deviceDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /杭州-运营机-01/ }),
  })
  await deviceDrawer.getByRole('button', { name: '查看应用' }).click()
  const applicationsDrawer = page.getByRole('dialog').filter({
    has: page.getByText('影刀应用列表', { exact: true }),
  })
  const configResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/automation-app-configs/yingdao/'),
  )
  await applicationsDrawer.getByRole('button', { name: '配置' }).first().click()
  await configResponse
  const dialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /配置参数 · 商品发布/ }),
  })
  await expect(dialog).toBeVisible()
  await waitForOverlayTransition(dialog)
  return { applicationsDrawer, dialog }
}

async function waitForOverlayTransition(dialog: Locator) {
  await expect
    .poll(
      () =>
        dialog.evaluate((element) => {
          const transform = getComputedStyle(element).transform
          if (transform === 'none') return 1
          return Math.round(new DOMMatrixReadOnly(transform).a * 1000) / 1000
        }),
      { timeout: 2_000 },
    )
    .toBe(1)
}

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('uses the shared management list pattern and capability-first drawer', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/shops')
  await page.getByText('设备中心', { exact: true }).click()

  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.getByRole('heading', { name: '设备中心' })).toHaveCount(0)
  const toolbar = page.getByRole('region', { name: '筛选条件' })
  await expect(toolbar.getByLabel('设备统计')).toBeVisible()
  await expect(toolbar.getByPlaceholder('搜索设备名称或影刀账号')).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '刷新' })).toBeVisible()
  await expect(toolbar.getByRole('button', { name: '添加设备' })).toBeVisible()

  for (const columnName of [
    '设备名称',
    '在线状态',
    '当前执行',
    '影刀',
    '影刀账号',
    '云端应用',
    '绑定店铺',
    '最后心跳',
    '启用',
    '操作',
  ]) {
    await expect(
      page.getByRole('columnheader', { name: columnName, exact: true }),
    ).toBeVisible()
  }
  await expect(page.getByTestId('device-monitor-icon').first()).toBeVisible()
  await expect(page.getByText('GY00999', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('未提供', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: '查看' }).first().click()
  const drawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /杭州-运营机-01/ }),
  })
  await expect(
    drawer.getByRole('heading', { name: /杭州-运营机-01/ }),
  ).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '运行概览' })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '执行能力' })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '影刀 RPA' })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '最近执行' })).toBeVisible()
  await expect(drawer.getByText('暂无可用的最近执行记录')).toBeVisible()
  await expect(drawer.getByText('CPU 摘要')).toHaveCount(0)
  await expect(drawer.getByText('内存摘要')).toHaveCount(0)
  await expect(drawer.getByText('系统', { exact: true })).toHaveCount(0)
  await expect(drawer.getByRole('button', { name: '查看应用' })).toBeEnabled()
  await expect(
    drawer.getByRole('button', { name: '刷新影刀能力' }),
  ).toBeDisabled()

  await drawer.getByRole('button', { name: '查看应用' }).click()
  const applicationsDrawer = page.getByRole('dialog').filter({
    has: page.getByText('影刀应用列表', { exact: true }),
  })
  await expect(applicationsDrawer).toBeVisible()
  await expect(
    applicationsDrawer.getByText('商品发布（Fixture）', { exact: true }),
  ).toBeVisible()
  await expect(
    applicationsDrawer.getByRole('columnheader', { name: '参数配置' }),
  ).toBeVisible()
  await expect(
    applicationsDrawer.getByRole('button', { name: '运行' }).first(),
  ).toBeVisible()
  await applicationsDrawer.getByRole('button', { name: '关闭' }).click()
  await drawer.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '添加设备' }).click()
  await expect(
    page.getByText('创建设备基础记录', { exact: true }).last(),
  ).toBeVisible()

  const layout = await page.evaluate(() => ({
    bodyOverflow: getComputedStyle(document.body).overflow,
    documentHasHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    bodyHasHorizontalOverflow:
      document.body.scrollWidth > document.body.clientWidth,
  }))
  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.documentHasHorizontalOverflow).toBe(false)
  expect(layout.bodyHasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])
})

test('fills remaining space and pins pagination for many, one and empty rows', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/devices')

  const section = page.locator('.device-list-section')
  const pagination = section.locator('.pagination-bar')
  const search = page.getByPlaceholder('搜索设备名称或影刀账号')

  const measure = async () => {
    const sectionBox = await section.boundingBox()
    const paginationBox = await pagination.boundingBox()
    if (!sectionBox || !paginationBox) throw new Error('设备列表布局不可测量')
    return {
      sectionHeight: Math.round(sectionBox.height),
      paginationY: Math.round(paginationBox.y),
      paginationBottomGap: Math.round(
        sectionBox.y +
          sectionBox.height -
          (paginationBox.y + paginationBox.height),
      ),
    }
  }

  await expect(page.getByText('杭州-运营机-01')).toBeVisible()
  const many = await measure()

  await search.fill('杭州-运营机-01')
  await expect(page.getByText('共 1 条')).toBeVisible()
  const one = await measure()

  await search.fill('完全不存在的设备')
  await expect(page.getByText('没有符合当前条件的设备')).toBeVisible()
  const empty = await measure()

  expect(one).toEqual(many)
  expect(empty).toEqual(many)
  await expect(section).toHaveCSS('flex-grow', '1')
})

test('persists enable state, protects active tasks and soft-removes idle devices', async ({
  page,
}) => {
  await page.goto('/#/devices')

  const idleRow = page.getByRole('row').filter({ hasText: '杭州-运营机-01' })
  await idleRow.getByRole('button', { name: '停用' }).click()
  await expect(idleRow.getByText('已停用', { exact: true })).toBeVisible()
  await idleRow.getByRole('button', { name: '启用' }).click()
  await expect(idleRow.getByText('已启用', { exact: true })).toBeVisible()

  const busyRow = page.getByRole('row').filter({ hasText: '上海-直播机-02' })
  await busyRow.getByRole('button', { name: '移除' }).click()
  await page.getByRole('button', { name: '确认移除' }).click()
  await expect(
    page.getByText('设备存在待执行或执行中的任务，暂时不能移除'),
  ).toBeVisible()
  await expect(busyRow).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await idleRow.getByRole('button', { name: '移除' }).click()
  await expect(page.getByText('Worker Token 立即失效')).toBeVisible()
  await page.getByRole('button', { name: '确认移除' }).click()
  await expect(page.getByText('杭州-运营机-01', { exact: true })).toHaveCount(0)
})

test('configures and tests a system webhook without revealing its URL', async ({
  page,
}) => {
  await page.goto('/#/devices')
  await page.getByText('系统设置', { exact: true }).click()
  await expect(page).toHaveURL(/#\/settings\/notifications$/)
  await expect(page.getByRole('heading', { name: '通知配置' })).toBeVisible()

  await page.getByRole('button', { name: '新增通道' }).click()
  await page.getByPlaceholder('例如：运营告警群').fill('设备告警群')
  await page
    .getByPlaceholder('请输入群机器人 Webhook URL')
    .fill('https://example.test/webhook/super-secret')
  await page.getByRole('button', { name: '保存配置' }).click()
  await expect(page.getByText('通知配置已保存').last()).toBeVisible()
  await expect(page.getByText('Webhook 已配置')).toBeVisible()
  await expect(page.getByText('super-secret')).toHaveCount(0)

  await page.getByRole('button', { name: '保存配置' }).click()
  await expect(page.getByText('通知配置已保存').last()).toBeVisible()
  await page.getByRole('button', { name: '发送测试通知' }).click()
  await expect(page.getByText('测试通知已发送')).toBeVisible()

  for (const theme of ['深色', '浅色']) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.getByText(theme, { exact: true }).click()
    await expect(page.getByRole('heading', { name: '通知配置' })).toBeVisible()
  }
})

test('keeps a growing application parameter form inside one dialog body scroll', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  const config = await mockAutomationConfig(page, 0)
  await page.goto('/#/devices')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  const { applicationsDrawer, dialog } = await openAutomationConfig(page)
  const rows = dialog.getByTestId('parameter-config-field')
  const addButton = dialog.getByRole('button', { name: '添加参数' })
  const header = dialog.locator(':scope > .n-card-header')
  const footer = dialog.locator(':scope > .n-card__footer')
  const body = dialog.locator(
    ':scope > .n-card__content-scrollbar > .n-scrollbar-container',
  )
  const pageScrollBefore = await page
    .locator('.app-shell__content')
    .evaluate((element) => element.scrollTop)

  await expect(rows).toHaveCount(0)
  const emptyMetrics = await body.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }))
  expect(emptyMetrics.scrollHeight).toBeLessThanOrEqual(emptyMetrics.clientHeight + 1)

  for (const targetCount of [1, 3, 10, 20]) {
    while ((await rows.count()) < targetCount) await addButton.click()
    await expect(rows).toHaveCount(targetCount)
    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.y).toBeGreaterThanOrEqual(54)
    expect(box!.y + box!.height).toBeLessThanOrEqual(768)
    await expect(header).toBeVisible()
    await expect(footer).toBeVisible()
    const metrics = await body.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    if (targetCount === 1) {
      expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 1)
    }
    if (targetCount >= 10) {
      expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)
    }
  }

  await expect(rows.last()).toBeInViewport()
  const overflowMetrics = await body.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }))
  expect(overflowMetrics.scrollHeight).toBeGreaterThan(overflowMetrics.clientHeight)

  const fixedBefore = {
    header: (await header.boundingBox())!.y,
    footer: (await footer.boundingBox())!.y,
  }
  await body.evaluate((element) => element.scrollTo({ top: element.scrollHeight }))
  const fixedAfter = {
    header: (await header.boundingBox())!.y,
    footer: (await footer.boundingBox())!.y,
  }
  expect(fixedAfter).toEqual(fixedBefore)

  const verticalScrollContainers = await dialog.evaluate((root) =>
    [...root.querySelectorAll<HTMLElement>('*')].filter((element) => {
      const overflowY = getComputedStyle(element).overflowY
      return (
        element.scrollHeight > element.clientHeight + 1 &&
        (overflowY === 'auto' || overflowY === 'scroll')
      )
    }).length,
  )
  expect(verticalScrollContainers).toBe(1)
  expect(
    await page.locator('.app-shell__content').evaluate((element) => element.scrollTop),
  ).toBe(pageScrollBefore)

  const scrollBeforeDelete = await body.evaluate((element) => element.scrollTop)
  await rows.last().getByRole('button', { name: '删除参数' }).click()
  await expect(rows).toHaveCount(19)
  expect(await body.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
  expect(scrollBeforeDelete).toBeGreaterThan(0)

  await dialog.getByRole('button', { name: '保存' }).click()
  await expect(dialog).toHaveCount(0)
  expect(config.savedFields()).toHaveLength(19)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await applicationsDrawer.getByRole('button', { name: '配置' }).first().click()
  const darkDialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /配置参数 · 商品发布/ }),
  })
  await expect(darkDialog).toBeVisible()
  await expect(darkDialog.getByTestId('parameter-config-field')).toHaveCount(19)
  const darkBox = await darkDialog.boundingBox()
  expect(darkBox!.y + darkBox!.height).toBeLessThanOrEqual(768)
  await darkDialog.getByRole('button', { name: '取消' }).click()
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps a 20-parameter dialog inside ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await mockAutomationConfig(page, 20)
    const { dialog } = await openAutomationConfig(page)
    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.y).toBeGreaterThanOrEqual(54)
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height)
    await expect(dialog.locator(':scope > .n-card-header')).toBeVisible()
    await expect(dialog.locator(':scope > .n-card__footer')).toBeVisible()
    const body = dialog.locator(
      ':scope > .n-card__content-scrollbar > .n-scrollbar-container',
    )
    const metrics = await body.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }))
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)
    const horizontalOverflow = await page.evaluate(() => ({
      document:
        document.documentElement.scrollWidth > document.documentElement.clientWidth,
      body: document.body.scrollWidth > document.body.clientWidth,
    }))
    expect(horizontalOverflow).toEqual({ document: false, body: false })
  })
}

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps Device Center inside ${viewport.width}×${viewport.height} in Light and Dark`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/devices')
    await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
    await expect(page.getByText('杭州-运营机-01')).toBeVisible()

    for (const theme of ['浅色', '深色']) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page.getByText(theme, { exact: true }).click()
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
