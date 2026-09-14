import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-08-24T12:00:00+08:00'))
})

test('uses the automation navigation group and renders every Task state', async ({
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
  await expect(page.getByText('设备中心', { exact: true })).toBeVisible()
  await page.getByText('任务中心', { exact: true }).click()

  await expect(page).toHaveURL(/#\/tasks$/)
  await expect(page.getByRole('heading', { name: '任务中心' })).toHaveCount(0)
  await expect(page.getByText('定时计划', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()

  for (const column of [
    '状态',
    '执行对象',
    '设备',
    '进度',
    '当前信息',
    '开始时间',
    '操作',
  ]) {
    await expect(
      page.getByRole('columnheader', { name: column, exact: true }),
    ).toBeVisible()
  }
  for (const status of ['待执行', '执行中', '成功', '失败', '丢失 / 中断']) {
    await expect(page.getByText(status, { exact: true }).first()).toBeVisible()
  }
  await expect(page.getByText('3 / 10', { exact: true })).toBeVisible()
  await expect(page.getByText('正在处理第 3 项', { exact: true })).toBeVisible()
  await expect(page.getByText('共 6 条', { exact: true })).toBeVisible()
  expect(runtimeErrors).toEqual([])
})

test('filters by status, device and stable searchable Task fields', async ({
  page,
}) => {
  await page.goto('/#/tasks')
  const toolbar = page.getByRole('region', { name: '筛选条件' })

  await toolbar.locator('.n-base-selection').nth(0).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '成功' })
    .click()
  await expect(page.getByText('系统回声验证', { exact: true })).toBeVisible()
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()

  await toolbar.getByRole('button', { name: '重置' }).click()
  await toolbar.locator('.n-base-selection').nth(1).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '上海-直播机-02' })
    .click()
  await expect(page.getByText('Python 进度闭环验证')).toBeVisible()
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()

  await toolbar.getByRole('button', { name: '重置' }).click()
  await toolbar
    .getByPlaceholder('搜索 Task ID / 执行对象 / Skill')
    .fill('yingdao.test')
  await expect(page.getByText('影刀无副作用测试').first()).toBeVisible()
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
})

test('defaults to seven days and resets from all-time without a second filter row', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/tasks')
  const toolbar = page.getByRole('region', { name: '筛选条件' })
  const selections = toolbar.locator('.n-base-selection')

  await expect(selections.nth(2)).toContainText('最近 7 天')
  await expect(page.getByText('共 6 条', { exact: true })).toBeVisible()
  await expect(page.getByText('历史审计任务', { exact: true })).toHaveCount(0)

  await selections.nth(2).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '全部时间' })
    .click()
  await expect(page.getByText('历史审计任务', { exact: true })).toBeVisible()
  await expect(page.getByText('共 7 条', { exact: true })).toBeVisible()

  await toolbar.getByRole('button', { name: '重置' }).click()
  await expect(selections.nth(2)).toContainText('最近 7 天')
  await expect(page.getByText('历史审计任务', { exact: true })).toHaveCount(0)

  await selections.nth(2).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '昨天' })
    .click()
  await expect(page.getByText('暂无任务')).toBeVisible()

  await selections.nth(2).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '今天' })
    .click()
  await expect(page.getByText('共 6 条', { exact: true })).toBeVisible()

  await selections.nth(2).click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '自定义' })
    .click()
  await expect(toolbar.locator('.n-date-picker')).toBeVisible()
  await expect(page.getByText('共 6 条', { exact: true })).toBeVisible()

  const filterRows = await toolbar
    .locator('.filter-bar__fields')
    .evaluate((node) => {
      const children = [...node.children] as HTMLElement[]
      return new Set(children.map((child) => Math.round(child.offsetTop))).size
    })
  expect(filterRows).toBe(1)
})

test('reuses TaskRuntimeDrawer for pending, running and terminal tasks', async ({
  page,
}) => {
  await page.goto('/#/tasks')

  const pendingRow = page.getByRole('row').filter({ hasText: '拼多多工单处理' })
  await pendingRow.getByRole('button', { name: '详情' }).click()
  let drawer = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(drawer.getByText('待执行', { exact: true })).toBeVisible()
  await expect(drawer.getByText('暂无运行日志')).toBeVisible()
  await drawer.getByRole('button', { name: '关闭' }).click()

  const runningRow = page
    .getByRole('row')
    .filter({ hasText: 'Python 进度闭环验证' })
  await runningRow.getByRole('button', { name: '详情' }).click()
  drawer = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(drawer.getByText('正在处理第 3 项').first()).toBeVisible()
  await expect(drawer.getByText('3 / 10', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '关闭' }).click()

  const failedRow = page
    .getByRole('row')
    .filter({ hasText: '影刀无副作用测试' })
  await failedRow.getByRole('button', { name: '详情' }).click()
  drawer = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(drawer.getByRole('heading', { name: '失败原因' })).toBeVisible()
  await expect(drawer.getByText('影刀运行时返回失败')).toBeVisible()
  await expect(drawer.getByText('错误码：RUNTIME_FAILED')).toBeVisible()
  await expect(
    drawer.getByText('该任务的历史运行日志已按保留策略清理。').first(),
  ).toBeVisible()
})

test('loads historical Runtime Events incrementally and distinguishes partial purge', async ({
  page,
}) => {
  await page.goto('/#/tasks')

  const successRow = page.getByRole('row').filter({ hasText: '系统回声验证' })
  await successRow.getByRole('button', { name: '详情' }).click()
  let drawer = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(drawer.locator('.task-runtime__log-viewport li')).toHaveCount(
    100,
  )
  await drawer.getByRole('button', { name: '加载更早' }).click()
  await expect(drawer.locator('.task-runtime__log-viewport li')).toHaveCount(
    200,
  )
  await expect(drawer.getByText('历史日志 6', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '关闭' }).click()

  const lostRow = page.getByRole('row').filter({ hasText: 'Worker 失联验证' })
  await lostRow.getByRole('button', { name: '详情' }).click()
  drawer = page.getByRole('dialog').filter({ hasText: '运行详情' })
  await expect(
    drawer.getByText('部分历史运行日志已按保留策略清理。').first(),
  ).toBeVisible()
  await expect(
    drawer
      .locator('.task-runtime__log-viewport li')
      .getByText('Worker 已领取任务'),
  ).toBeVisible()
})

test('fills remaining space and pins pagination for many, one and empty states', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/tasks')
  const section = page.locator('.task-list-section')
  const pagination = section.locator('.pagination-bar')
  const search = page.getByPlaceholder('搜索 Task ID / 执行对象 / Skill')

  const measure = async () => {
    const sectionBox = await section.boundingBox()
    const paginationBox = await pagination.boundingBox()
    if (!sectionBox || !paginationBox) throw new Error('任务列表布局不可测量')
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

  const many = await measure()
  await search.fill('系统回声验证')
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
  const one = await measure()
  await search.fill('完全不存在的任务')
  await expect(page.getByText(/暂无任务/)).toBeVisible()
  const empty = await measure()

  expect(one).toEqual(many)
  expect(empty).toEqual(many)
  await expect(section).toHaveCSS('flex-grow', '1')
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps Task Center inside ${viewport.width}×${viewport.height} in Light and Dark`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/tasks')
    await expect(page.getByText('原子模式单店模式')).toBeVisible()

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
