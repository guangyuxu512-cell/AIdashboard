import { expect, test } from '@playwright/test'

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
  await page.getByText('自动化中心', { exact: true }).click()
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
  await expect(drawer.getByRole('button', { name: '查看能力' })).toBeEnabled()
  await expect(drawer.getByRole('button', { name: '编辑' })).toBeVisible()
  await expect(
    drawer.getByRole('button', { name: '刷新影刀能力' }),
  ).toBeDisabled()

  await drawer.getByRole('button', { name: '查看能力' }).click()
  const applicationsDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /设备能力 · 杭州-运营机-01/ }),
  })
  await expect(applicationsDrawer).toBeVisible()
  await expect(
    applicationsDrawer.getByRole('heading', { name: '业务 Skill' }),
  ).toBeVisible()
  await expect(
    applicationsDrawer.getByRole('heading', { name: '影刀应用' }),
  ).toBeVisible()
  await expect(
    applicationsDrawer.getByText('暂无业务 Skill', { exact: false }),
  ).toBeVisible()
  await expect(
    applicationsDrawer.getByText('yingdao.app.run', { exact: true }),
  ).toHaveCount(0)
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

test('uses the same app-filtered parameter library from a Yingdao application', async ({
  page,
}) => {
  const appId = 'app-fixture-product-publish-1'
  let filteredRequest = false

  await page.route('**/api/v1/automation-app-configs/yingdao/applications*', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        { app_id: appId, app_name: '商品发布（Fixture）' },
      ]),
    }),
  )
  await page.route('**/api/v1/automation-parameter-presets*', (route) => {
    const params = new URL(route.request().url()).searchParams
    filteredRequest =
      params.get('app_id') === appId &&
      params.get('device_id') === 'device-fixture-001'
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
    })
  })

  await page.goto('/#/devices')
  await page.getByRole('button', { name: '能力' }).first().click()
  const capabilityDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /设备能力 · 杭州-运营机-01/ }),
  })
  await capabilityDrawer
    .getByRole('button', { name: '参数配置', exact: true })
    .first()
    .click()

  await expect(page).toHaveURL(
    /#\/parameter-presets\?device_id=device-fixture-001&app_id=app-fixture-product-publish-1$/,
  )
  await expect.poll(() => filteredRequest).toBe(true)
  await expect(page.getByRole('button', { name: '+ 新建配置' })).toBeVisible()
  await expect(capabilityDrawer).toHaveCount(0)
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
