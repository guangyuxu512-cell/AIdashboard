import { expect, test, type Page, type Route } from '@playwright/test'

const viewportWidths = [360, 375, 390, 430] as const
const themes = ['light', 'dark'] as const
const safeAreaFixture = {
  top: '19px',
  right: '22px',
  bottom: '23px',
  left: '21px',
} as const

type TaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'lost'

interface MockApiOptions {
  failTaskPage2Once?: boolean
  failDevicePage2Once?: boolean
  emptyThenBackgroundFailure?: boolean
}

interface MockApiState {
  taskListRequests: string[]
  deviceListRequests: string[]
  eventRequests: string[]
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function applySafeAreaFixture(page: Page): Promise<void> {
  await page.evaluate((safeArea) => {
    const root = document.documentElement
    root.style.setProperty('--safe-area-top', safeArea.top)
    root.style.setProperty('--safe-area-right', safeArea.right)
    root.style.setProperty('--safe-area-bottom', safeArea.bottom)
    root.style.setProperty('--safe-area-left', safeArea.left)
  }, safeAreaFixture)
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true)
}

async function countCardsInsideMainViewport(
  page: Page,
  selector: string,
): Promise<number> {
  return page.locator(selector).evaluateAll((elements) => {
    const main = document
      .querySelector<HTMLElement>('.mobile-app-shell__main')
      ?.getBoundingClientRect()
    if (!main) return 0
    return elements.filter((element) => {
      const card = element.getBoundingClientRect()
      return card.top >= main.top && card.bottom <= main.bottom
    }).length
  })
}

function taskStatusFor(index: number): TaskStatus {
  const statuses: readonly TaskStatus[] = [
    'running',
    'pending',
    'failed',
    'lost',
    'success',
  ]
  return statuses[(index - 1) % statuses.length] ?? 'pending'
}

function makeTaskListItem(index: number, special = false) {
  const taskId = special ? 'task-101' : `task-${index}`
  const status = special ? 'success' : taskStatusFor(index)
  const deviceIndex = special ? 101 : index
  return {
    task_id: taskId,
    target_device_id: `device-${deviceIndex}`,
    device_display_name: `设备 ${deviceIndex}`,
    skill_id: special ? 'special-sync' : `skill-${index}`,
    skill_display_name: special ? '专项技能' : `技能 ${index}`,
    execution_display_name: special ? '专项同步' : `执行任务 ${index}`,
    status,
    progress: status === 'running' ? { current: index, total: 30 } : null,
    current_message: status === 'running' ? `正在处理第 ${index} 项` : null,
    started_at: status === 'pending' ? null : '2026-08-26T01:00:00.000Z',
    finished_at:
      status === 'success' || status === 'failed' || status === 'lost'
        ? '2026-08-26T01:05:00.000Z'
        : null,
    created_at: '2026-08-26T00:55:00.000Z',
  }
}

const taskItems = [
  ...Array.from({ length: 25 }, (_, index) => makeTaskListItem(index + 1)),
  makeTaskListItem(101, true),
]

function makeTaskDetail(taskId: string) {
  const isSpecial = taskId === 'task-101'
  const isLongError = taskId === 'task-error'
  const numericId = Number(taskId.replace('task-', '')) || 1
  const status: TaskStatus = isSpecial
    ? 'success'
    : isLongError
      ? 'failed'
      : taskStatusFor(numericId)
  const deviceIndex = isSpecial ? 101 : 1
  return {
    task_id: taskId,
    target_device_id: `device-${deviceIndex}`,
    shop_ids: ['shop-1', 'shop-2'],
    asset_ids: [],
    skill_id: isSpecial ? 'special-sync' : 'skill-1',
    execution_display_name: isSpecial ? '专项同步' : '订单同步',
    status,
    input: { secret: '不得展示' },
    result: isSpecial
      ? { summary: '已安全同步 20 个店铺', private_data: '不得展示' }
      : null,
    error_code: isLongError ? 'E'.repeat(64) : null,
    error_message: isLongError ? '已脱敏的失败原因' : null,
    lease_until: null,
    started_at: status === 'pending' ? null : '2026-08-26T01:00:00.000Z',
    finished_at:
      status === 'success' || status === 'failed' || status === 'lost'
        ? '2026-08-26T01:05:00.000Z'
        : null,
    runtime_events_purged_at: null,
    created_at: '2026-08-26T00:55:00.000Z',
    updated_at: '2026-08-26T01:05:00.000Z',
  }
}

function makeDevice(index: number) {
  return {
    device_id: `device-${index}`,
    display_name: `设备 ${index}`,
    enabled: true,
    location: null,
    note: null,
    deleted_at: null,
    worker_runtime: null,
    created_at: '2026-08-01T00:00:00.000Z',
    updated_at: '2026-08-26T00:00:00.000Z',
  }
}

function makeEvent(taskId: string, sequence: number) {
  const isProgress = sequence === 200 && taskId !== 'task-error'
  return {
    event_id: `event-${taskId}-${sequence}`,
    task_id: taskId,
    seq: sequence,
    event_type: isProgress ? 'progress' : 'log',
    level: 'info',
    message: isProgress ? '已处理 20 个店铺' : `纯文本日志 ${sequence}`,
    event_at: '2026-08-26T01:00:00.000Z',
    metadata: isProgress ? { current: 20, total: 20 } : {},
    created_at: '2026-08-26T01:00:00.000Z',
  }
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function fulfillApiError(route: Route, message: string): Promise<void> {
  await route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({
      code: 'DATABASE_OPERATION_FAILED',
      message,
      request_id: 'request-e2e',
      details: null,
    }),
  })
}

async function installMockApi(
  page: Page,
  options: MockApiOptions = {},
): Promise<MockApiState> {
  const state: MockApiState = {
    taskListRequests: [],
    deviceListRequests: [],
    eventRequests: [],
  }
  let taskPage2Failed = false
  let devicePage2Failed = false
  let taskListResponseCount = 0

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const relativePath = url.pathname.replace(/^.*\/api\/v1\//, '')

    const eventMatch = relativePath.match(/^tasks\/([^/]+)\/events$/)
    if (eventMatch) {
      const taskId = decodeURIComponent(eventMatch[1] ?? '')
      state.eventRequests.push(url.toString())
      const beforeSequence = url.searchParams.get('before_seq')
      const afterSequence = url.searchParams.get('after_seq')

      if (beforeSequence !== null) {
        return fulfillJson(route, {
          task_id: taskId,
          after_seq: null,
          before_seq: Number(beforeSequence),
          next_after_seq: 100,
          next_before_seq: 1,
          has_more_before: false,
          items: Array.from({ length: 100 }, (_, index) =>
            makeEvent(taskId, index + 1),
          ),
        })
      }

      if (afterSequence !== null) {
        return fulfillJson(route, {
          task_id: taskId,
          after_seq: Number(afterSequence),
          before_seq: null,
          next_after_seq: Number(afterSequence),
          next_before_seq: null,
          has_more_before: false,
          items: [],
        })
      }

      return fulfillJson(route, {
        task_id: taskId,
        after_seq: null,
        before_seq: null,
        next_after_seq: 200,
        next_before_seq: 101,
        has_more_before: true,
        items: Array.from({ length: 100 }, (_, index) =>
          makeEvent(taskId, index + 101),
        ),
      })
    }

    const taskDetailMatch = relativePath.match(/^tasks\/([^/]+)$/)
    if (taskDetailMatch) {
      return fulfillJson(
        route,
        makeTaskDetail(decodeURIComponent(taskDetailMatch[1] ?? '')),
      )
    }

    if (relativePath === 'tasks') {
      state.taskListRequests.push(url.toString())
      taskListResponseCount += 1
      const pageNumber = Number(url.searchParams.get('page') ?? 1)

      if (options.emptyThenBackgroundFailure && taskListResponseCount > 1) {
        return fulfillApiError(route, '任务后台刷新失败')
      }
      if (options.failTaskPage2Once && pageNumber === 2 && !taskPage2Failed) {
        taskPage2Failed = true
        return fulfillApiError(route, '下一页任务加载失败')
      }

      if (options.emptyThenBackgroundFailure) {
        return fulfillJson(route, {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        })
      }

      const status = url.searchParams.get('status')
      const deviceId = url.searchParams.get('device_id')
      const search = url.searchParams.get('search')?.trim()
      let filtered = taskItems
      if (status) filtered = filtered.filter((task) => task.status === status)
      if (deviceId) {
        filtered = filtered.filter((task) => task.target_device_id === deviceId)
      }
      if (search) {
        filtered = filtered.filter((task) =>
          task.execution_display_name.includes(search),
        )
      }
      const start = (pageNumber - 1) * 20
      return fulfillJson(route, {
        items: filtered.slice(start, start + 20),
        total: filtered.length,
        page: pageNumber,
        page_size: 20,
      })
    }

    const deviceDetailMatch = relativePath.match(/^devices\/([^/]+)$/)
    if (deviceDetailMatch) {
      const deviceId = decodeURIComponent(deviceDetailMatch[1] ?? '')
      const index = Number(deviceId.replace('device-', '')) || 1
      return fulfillJson(route, makeDevice(index))
    }

    if (relativePath === 'devices') {
      state.deviceListRequests.push(url.toString())
      const pageNumber = Number(url.searchParams.get('page') ?? 1)
      if (
        options.failDevicePage2Once &&
        pageNumber === 2 &&
        !devicePage2Failed
      ) {
        devicePage2Failed = true
        return fulfillApiError(route, '下一页设备加载失败')
      }
      const first = (pageNumber - 1) * 100 + 1
      const last = Math.min(pageNumber * 100, 101)
      return fulfillJson(route, {
        items:
          first > last
            ? []
            : Array.from({ length: last - first + 1 }, (_, index) =>
                makeDevice(first + index),
              ),
        total: 101,
        page: pageNumber,
        page_size: 100,
      })
    }

    await fulfillApiError(route, `未处理的测试路径：${relativePath}`)
  })

  return state
}

async function setThemeBeforeNavigation(
  page: Page,
  theme: (typeof themes)[number],
): Promise<void> {
  await page.addInitScript((mode) => {
    window.localStorage.setItem('control-center.mobile.theme-mode', mode)
  }, theme)
}

async function chooseDatePreset(page: Page, label: string): Promise<void> {
  await page.getByTestId('date-filter').click()
  const picker = page.locator('.task-filter-sheet__preset-popup')
  await expect(picker).toBeVisible()
  await picker
    .locator('.van-picker-column__item')
    .filter({ hasText: new RegExp(`^${label}$`) })
    .click()
  await picker.locator('.van-picker__confirm').click()
}

async function scrollMainToBottom(page: Page): Promise<void> {
  await page.locator('.mobile-app-shell__main').evaluate((element) => {
    element.scrollTop = element.scrollHeight
    element.dispatchEvent(new Event('scroll'))
  })
}

async function scrollDevicePopupToBottom(page: Page): Promise<void> {
  await page.locator('.task-filter-sheet__device-popup').evaluate((element) => {
    element.scrollTop = element.scrollHeight
    element.dispatchEvent(new Event('scroll'))
  })
}

async function pullToRefresh(page: Page): Promise<void> {
  const main = page.locator('.mobile-app-shell__main')
  await main.evaluate((element) => {
    element.scrollTop = 0
  })
  const box = await page.locator('.van-pull-refresh__track').boundingBox()
  if (!box) throw new Error('未找到下拉刷新触控区域')

  const client = await page.context().newCDPSession(page)
  const x = box.x + Math.min(box.width / 2, 120)
  const startY = box.y + 30
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x, y: startY }],
  })
  for (const offset of [35, 70, 105, 140]) {
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x, y: startY + offset }],
    })
  }
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchEnd',
    touchPoints: [],
  })
  await client.detach()
}

for (const width of viewportWidths) {
  for (const theme of themes) {
    test(`任务中心 ${width}px ${theme} 主题保持完整页面、安全区与零溢出`, async ({
      page,
    }, testInfo) => {
      const consoleErrors = collectConsoleErrors(page)
      await page.setViewportSize({ width, height: 844 })
      await setThemeBeforeNavigation(page, theme)
      await installMockApi(page)
      await page.goto('/#/tasks')
      await applySafeAreaFixture(page)

      await expect(page.getByTestId('task-card').first()).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const firstCardBox = await page
        .locator('.task-list__item')
        .first()
        .boundingBox()
      expect(firstCardBox?.height).toBeGreaterThanOrEqual(44)
      expect(firstCardBox?.height).toBeLessThan(150)
      await expect(
        page.locator('.task-list__item').nth(1).locator('.van-progress'),
      ).toHaveCount(0)
      expect(
        await countCardsInsideMainViewport(page, '.task-list__item'),
      ).toBeGreaterThanOrEqual(4)

      const titleStyle = await page
        .locator('.task-list-card__heading h2')
        .first()
        .evaluate((element) => {
          const style = window.getComputedStyle(element)
          return {
            overflow: style.overflow,
            textOverflow: style.textOverflow,
            whiteSpace: style.whiteSpace,
          }
        })
      expect(titleStyle).toEqual({
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      })

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`task-list-390-${theme}.png`),
        })
      }

      const layout = await page.evaluate(() => {
        const style = (selector: string) => {
          const element = document.querySelector<HTMLElement>(selector)
          if (!element) throw new Error(`未找到布局节点：${selector}`)
          return window.getComputedStyle(element)
        }
        const main = document
          .querySelector<HTMLElement>('.mobile-app-shell__main')
          ?.getBoundingClientRect()
        const footer = document
          .querySelector<HTMLElement>('.mobile-app-shell__bottom')
          ?.getBoundingClientRect()
        const tabbar = document
          .querySelector<HTMLElement>('.van-tabbar')
          ?.getBoundingClientRect()
        return {
          tabsLeft: style('.task-center-page__tabs').paddingLeft,
          tabsRight: style('.task-center-page__tabs').paddingRight,
          toolbarLeft: style('.task-center-page__toolbar').paddingLeft,
          toolbarRight: style('.task-center-page__toolbar').paddingRight,
          listLeft: style('.task-list').paddingLeft,
          listRight: style('.task-list').paddingRight,
          footerBottom: style('.mobile-app-shell__bottom').paddingBottom,
          tabbarPosition: style('.van-tabbar').position,
          mainBottom: main?.bottom ?? 0,
          footerTop: footer?.top ?? 0,
          tabbarBottom: tabbar?.bottom ?? 0,
          footerBottomEdge: footer?.bottom ?? 0,
        }
      })
      expect(layout).toMatchObject({
        tabsLeft: safeAreaFixture.left,
        tabsRight: safeAreaFixture.right,
        toolbarLeft: safeAreaFixture.left,
        toolbarRight: safeAreaFixture.right,
        listLeft: safeAreaFixture.left,
        listRight: safeAreaFixture.right,
        footerBottom: safeAreaFixture.bottom,
      })
      expect(layout.tabbarPosition).not.toBe('fixed')
      expect(layout.mainBottom).toBeLessThanOrEqual(layout.footerTop + 1)
      expect(layout.tabbarBottom).toBeLessThanOrEqual(
        layout.footerBottomEdge - 23 + 1,
      )

      await page.getByTestId('open-filter').click()
      const filter = page.locator('.task-filter-sheet')
      await expect(filter).toBeVisible()
      const filterSafeArea = await filter.evaluate((element) => {
        const style = window.getComputedStyle(element)
        return {
          right: style.paddingRight,
          bottom: style.paddingBottom,
          left: style.paddingLeft,
        }
      })
      expect(filterSafeArea).toEqual({
        right: safeAreaFixture.right,
        bottom: '39px',
        left: safeAreaFixture.left,
      })
      await expectNoHorizontalOverflow(page)
      await chooseDatePreset(page, '自定义')
      const calendar = page.locator('.task-filter-sheet__calendar')
      await expect(calendar).toBeVisible()
      expect(
        await calendar.evaluate((element) => {
          const style = window.getComputedStyle(element)
          return {
            right: style.paddingRight,
            left: style.paddingLeft,
          }
        }),
      ).toEqual({
        right: safeAreaFixture.right,
        left: safeAreaFixture.left,
      })
      await expectNoHorizontalOverflow(page)
      await calendar.locator('.van-calendar__confirm').click()
      await page.getByTestId('apply-filter').click()

      await page.locator('.task-list__item').first().click()
      await expect(page.getByTestId('task-detail')).toBeVisible()
      await expect(page.getByTestId('runtime-events')).toBeVisible()
      const moreInformation = page.getByTestId('task-more-information')
      await expect(
        moreInformation.locator('.van-collapse-item__content'),
      ).toBeHidden()
      if (width === 390 && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath('task-detail-390-light.png'),
        })
      }
      await expect(page.locator('.van-tabbar')).toHaveCount(0)
      await expectNoHorizontalOverflow(page)
      expect(consoleErrors).toEqual([])
    })
  }
}

test('筛选、完整分页、下拉刷新、终态日志补齐与返回形成闭环', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks')
  await applySafeAreaFixture(page)

  await expect(page.getByTestId('task-card').first()).toBeVisible()
  expect(await page.locator('.van-tab').allTextContents()).toEqual([
    '全部',
    '待执行',
    '执行中',
    '成功',
    '失败',
    '已丢失',
  ])
  const initialRequest = new URL(state.taskListRequests[0] ?? '')
  expect(initialRequest.searchParams.has('created_from')).toBe(true)
  expect(initialRequest.searchParams.has('created_to')).toBe(true)

  await scrollMainToBottom(page)
  await expect(page.getByText('专项同步').first()).toBeVisible()

  await page
    .locator('.van-tab')
    .filter({ hasText: /^失败$/ })
    .click()
  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      return request ? new URL(request).searchParams.get('status') : null
    })
    .toBe('failed')
  await expect(page.getByText('失败').last()).toBeVisible()
  await page
    .locator('.van-tab')
    .filter({ hasText: /^全部$/ })
    .click()

  await page.getByTestId('open-filter').click()
  await chooseDatePreset(page, '全部时间')
  await page.getByTestId('apply-filter').click()
  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      if (!request) return null
      const params = new URL(request).searchParams
      return [params.has('created_from'), params.has('created_to')]
    })
    .toEqual([false, false])

  await page.getByTestId('open-filter').click()
  const searchInput = page.locator('.task-filter-sheet .van-search input')
  await searchInput.fill('x'.repeat(501))
  await expect(searchInput).toHaveValue('x'.repeat(500))
  await searchInput.fill('专项')

  await page.getByTestId('device-filter').click()
  const devicePopup = page.locator('.task-filter-sheet__device-popup')
  await expect(devicePopup.getByText('设备 1', { exact: true })).toBeVisible()
  await expect(devicePopup).not.toContainText('device-1')
  expect(
    await devicePopup.evaluate((element) => {
      const style = window.getComputedStyle(element)
      return {
        right: style.paddingRight,
        bottom: style.paddingBottom,
        left: style.paddingLeft,
      }
    }),
  ).toEqual({
    right: safeAreaFixture.right,
    bottom: safeAreaFixture.bottom,
    left: safeAreaFixture.left,
  })
  await scrollDevicePopupToBottom(page)
  await expect(devicePopup.getByText('设备 101', { exact: true })).toBeVisible()
  expect(
    state.deviceListRequests.some(
      (request) => new URL(request).searchParams.get('page') === '2',
    ),
  ).toBe(true)
  await devicePopup.getByText('设备 101', { exact: true }).click()

  await chooseDatePreset(page, '自定义')
  const calendar = page.locator('.van-calendar')
  await expect(calendar).toBeVisible()
  await calendar.locator('.van-calendar__confirm').click()
  await page.getByTestId('apply-filter').click()

  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      if (!request) return null
      const params = new URL(request).searchParams
      return {
        search: params.get('search'),
        device: params.get('device_id'),
        hasFrom: params.has('created_from'),
        hasTo: params.has('created_to'),
      }
    })
    .toEqual({
      search: '专项',
      device: 'device-101',
      hasFrom: true,
      hasTo: true,
    })
  await expect(page.getByText('专项同步').first()).toBeVisible()

  const requestCountBeforeRefresh = state.taskListRequests.length
  await pullToRefresh(page)
  await expect
    .poll(() => state.taskListRequests.length)
    .toBeGreaterThan(requestCountBeforeRefresh)

  await page.locator('.task-list__item').first().click()
  await expect(page.getByText('已安全同步 20 个店铺')).toBeVisible()
  await expect(page.getByText('不得展示')).toHaveCount(0)
  await expect(page.getByTestId('runtime-events')).toContainText('#200')
  await page.getByText('更多信息', { exact: true }).click()
  await expect(page.getByText('任务 ID', { exact: true })).toBeVisible()
  await expect(page.getByText('技能 ID', { exact: true })).toBeVisible()
  await expect(page.getByText('设备 ID', { exact: true })).toBeVisible()
  await expect
    .poll(() =>
      state.eventRequests.some(
        (request) => new URL(request).searchParams.get('after_seq') === '200',
      ),
    )
    .toBe(true)

  await page.getByTestId('load-earlier-events').click()
  await expect(page.getByTestId('runtime-events')).toContainText('#1')
  expect(
    state.eventRequests.some(
      (request) => new URL(request).searchParams.get('before_seq') === '101',
    ),
  ).toBe(true)

  await page.locator('.van-nav-bar__left').click()
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await expect(page.locator('.van-tabbar')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})

test('六种日期预设使用本地自然日半开区间或完全省略日期参数', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card').first()).toBeVisible()

  const now = new Date()
  const startOfDay = (offset: number) =>
    new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate() + offset,
    ).toISOString()
  const presets = [
    ['今天', 0, 1],
    ['昨天', -1, 0],
    ['最近 7 天', -6, 1],
    ['最近 30 天', -29, 1],
  ] as const

  for (const [label, startOffset, endOffset] of presets) {
    await page.getByTestId('open-filter').click()
    await chooseDatePreset(page, label)
    await page.getByTestId('apply-filter').click()
    await expect
      .poll(() => {
        const request = state.taskListRequests.at(-1)
        if (!request) return null
        const params = new URL(request).searchParams
        return {
          from: params.get('created_from'),
          to: params.get('created_to'),
        }
      })
      .toEqual({ from: startOfDay(startOffset), to: startOfDay(endOffset) })
  }

  await page.getByTestId('open-filter').click()
  await chooseDatePreset(page, '自定义')
  await expect(page.locator('.van-calendar')).toBeVisible()
  await page.locator('.van-calendar__confirm').click()
  await page.getByTestId('apply-filter').click()
  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      if (!request) return null
      const params = new URL(request).searchParams
      return [params.has('created_from'), params.has('created_to')]
    })
    .toEqual([true, true])

  await page.getByTestId('open-filter').click()
  await chooseDatePreset(page, '全部时间')
  await page.getByTestId('apply-filter').click()
  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      if (!request) return null
      const params = new URL(request).searchParams
      return [params.has('created_from'), params.has('created_to')]
    })
    .toEqual([false, false])
})

test('任务和设备下一页错误保留已有数据并提供独立重试', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, {
    failTaskPage2Once: true,
    failDevicePage2Once: true,
  })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card').first()).toBeVisible()

  await scrollMainToBottom(page)
  await expect(page.getByTestId('task-next-page-error')).toBeVisible()
  await expect(page.getByTestId('background-error')).toHaveCount(0)
  await page
    .getByTestId('task-next-page-error')
    .getByRole('button', { name: '重试加载更多' })
    .click()
  await expect(page.getByText('专项同步').first()).toBeVisible()

  await page.getByTestId('open-filter').click()
  await page.getByTestId('device-filter').click()
  const devicePopup = page.locator('.task-filter-sheet__device-popup')
  await expect(devicePopup.getByText('设备 1', { exact: true })).toBeVisible()
  await scrollDevicePopupToBottom(page)
  await expect(page.getByTestId('device-next-page-error')).toBeVisible()
  await page
    .getByTestId('device-next-page-error')
    .getByRole('button', { name: '重试加载更多' })
    .click()
  await expect(devicePopup.getByText('设备 101', { exact: true })).toBeVisible()
})

test('成功空缓存后台失败仍展示空态与背景提示', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installMockApi(page, { emptyThenBackgroundFailure: true })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-empty')).toBeVisible()

  await expect(page.getByTestId('background-error')).toBeVisible({
    timeout: 7_000,
  })
  await expect(page.getByTestId('task-empty')).toBeVisible()
  await expect(page.getByTestId('task-error')).toHaveCount(0)
})

test('非终态详情持续发送 after_seq 增量请求', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks/task-1')
  await expect(page.getByTestId('runtime-events')).toBeVisible()
  const duration = page
    .locator('.van-cell')
    .filter({ hasText: '运行时间' })
    .locator('.van-cell__value')
  const firstDuration = await duration.textContent()
  await expect.poll(() => duration.textContent()).not.toBe(firstDuration)
  await expect
    .poll(
      () =>
        state.eventRequests.filter((request) =>
          new URL(request).searchParams.has('after_seq'),
        ).length,
    )
    .toBeGreaterThan(0)
  const firstLiveRequestCount = state.eventRequests.filter((request) =>
    new URL(request).searchParams.has('after_seq'),
  ).length
  await expect
    .poll(
      () =>
        state.eventRequests.filter((request) =>
          new URL(request).searchParams.has('after_seq'),
        ).length,
      { timeout: 4_500 },
    )
    .toBeGreaterThan(firstLiveRequestCount)
  expect(consoleErrors).toEqual([])
})

test('64 字符错误码在 360px 详情中可折行且不横向溢出', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 360, height: 800 })
  await installMockApi(page)
  await page.goto('/#/tasks/task-error')

  await expect(page.getByText('E'.repeat(64), { exact: true })).toBeVisible()
  await expect(page.getByTestId('detail-progress-value')).toHaveCount(0)
  await expect(page.getByTestId('detail-current-message')).toHaveText(
    '纯文本日志 200',
  )
  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})
