import { expect, test, type Page, type Route } from '@playwright/test'

import { createMobileAuthApiFixture } from './auth-api-fixture'

const viewports = [
  { width: 360, height: 640 },
  { width: 375, height: 740 },
  { width: 390, height: 844 },
  { width: 428, height: 926 },
  { width: 430, height: 932 },
] as const
const themes = ['light', 'dark'] as const
const safeAreaFixture = {
  top: '19px',
  right: '11px',
  bottom: '23px',
  left: '10px',
} as const

type TaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'lost'

interface MockApiOptions {
  taskTotal?: number
  empty?: boolean
  initialListDelayMs?: number
  failInitialListOnce?: boolean
  failRefreshOnce?: boolean
  failNextPageOnce?: boolean
}

interface MockApiState {
  listRequests: string[]
  metricRequests: string[]
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

async function setThemeBeforeNavigation(
  page: Page,
  theme: (typeof themes)[number],
): Promise<void> {
  await page.addInitScript((mode) => {
    window.localStorage.setItem('control-center.mobile.theme-mode', mode)
  }, theme)
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
  const status = special ? 'success' : taskStatusFor(index)
  return {
    task_id: special ? 'task-101' : `task-${index}`,
    target_device_id: special ? 'device-101' : `device-${index}`,
    device_display_name: special ? '专项设备' : `设备 ${index}`,
    skill_id: special ? 'special-sync' : `skill-${index}`,
    skill_display_name: special ? '专项技能' : `技能 ${index}`,
    execution_display_name: special
      ? '跨境电商多平台每日数据报表汇总与异常核对任务'
      : `执行任务 ${index}`,
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

const defaultTaskItems = [
  ...Array.from({ length: 25 }, (_, index) => makeTaskListItem(index + 1)),
  makeTaskListItem(101, true),
]

function makeTaskDetail(taskId: string) {
  const numericId = Number(taskId.replace('task-', '')) || 1
  const status = taskId === 'task-101' ? 'success' : taskStatusFor(numericId)
  return {
    task_id: taskId,
    target_device_id: `device-${numericId}`,
    shop_ids: [],
    asset_ids: [],
    skill_id: `skill-${numericId}`,
    execution_display_name: `执行任务 ${numericId}`,
    status,
    input: {},
    result: status === 'success' ? { summary: '已完成' } : null,
    error_code: null,
    error_message: null,
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

function makeDevice(deviceId: string) {
  return {
    device_id: deviceId,
    display_name: deviceId === 'device-1' ? '设备 1' : deviceId,
    enabled: true,
    location: null,
    note: null,
    deleted_at: null,
    worker_runtime: null,
    created_at: '2026-08-01T00:00:00.000Z',
    updated_at: '2026-08-26T00:00:00.000Z',
  }
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function fulfillApiError(route: Route): Promise<void> {
  await route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({
      code: 'DATABASE_OPERATION_FAILED',
      message: '仅供测试的技术错误',
      request_id: 'request-e2e',
      details: null,
    }),
  })
}

async function installMockApi(
  page: Page,
  options: MockApiOptions = {},
): Promise<MockApiState> {
  const auth = createMobileAuthApiFixture()
  const state: MockApiState = {
    listRequests: [],
    metricRequests: [],
    eventRequests: [],
  }
  let initialFailureUsed = false
  let pageOneSucceeded = false
  let refreshFailureUsed = false
  let nextPageFailureUsed = false

  await page.route('**/api/v1/**', async (route) => {
    if (await auth.handle(route)) return
    const url = new URL(route.request().url())
    const relativePath = url.pathname.replace(/^.*\/api\/v1\//, '')

    const eventMatch = relativePath.match(/^tasks\/([^/]+)\/events$/)
    if (eventMatch) {
      const taskId = decodeURIComponent(eventMatch[1] ?? '')
      state.eventRequests.push(url.toString())
      return fulfillJson(route, {
        task_id: taskId,
        after_seq: null,
        before_seq: null,
        next_after_seq: null,
        next_before_seq: null,
        has_more_before: false,
        items: [],
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
      const pageSize = Number(url.searchParams.get('page_size') ?? 20)
      const pageNumber = Number(url.searchParams.get('page') ?? 1)
      const isMetricRequest = pageSize === 1
      ;(isMetricRequest ? state.metricRequests : state.listRequests).push(
        url.toString(),
      )

      if (!isMetricRequest && pageNumber === 1 && options.initialListDelayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.initialListDelayMs),
        )
      }
      if (
        !isMetricRequest &&
        pageNumber === 1 &&
        options.failInitialListOnce &&
        !initialFailureUsed
      ) {
        initialFailureUsed = true
        return fulfillApiError(route)
      }
      if (
        !isMetricRequest &&
        pageNumber === 1 &&
        options.failRefreshOnce &&
        pageOneSucceeded &&
        !refreshFailureUsed
      ) {
        refreshFailureUsed = true
        return fulfillApiError(route)
      }
      if (
        !isMetricRequest &&
        pageNumber === 2 &&
        options.failNextPageOnce &&
        !nextPageFailureUsed
      ) {
        nextPageFailureUsed = true
        return fulfillApiError(route)
      }

      const allItems = options.empty
        ? []
        : options.taskTotal === undefined
          ? defaultTaskItems
          : Array.from({ length: options.taskTotal }, (_, index) =>
              makeTaskListItem(index + 1),
            )
      const status = url.searchParams.get('status')
      const search = url.searchParams.get('search')?.trim()
      let filtered = allItems
      if (status) filtered = filtered.filter((task) => task.status === status)
      if (search) {
        filtered = filtered.filter((task) =>
          task.execution_display_name.includes(search),
        )
      }
      const start = (pageNumber - 1) * pageSize
      if (!isMetricRequest && pageNumber === 1) pageOneSucceeded = true
      return fulfillJson(route, {
        items: filtered.slice(start, start + pageSize),
        total: filtered.length,
        page: pageNumber,
        page_size: pageSize,
      })
    }

    const deviceDetailMatch = relativePath.match(/^devices\/([^/]+)$/)
    if (deviceDetailMatch) {
      return fulfillJson(
        route,
        makeDevice(decodeURIComponent(deviceDetailMatch[1] ?? '')),
      )
    }

    await fulfillApiError(route)
  })

  return state
}

async function scrollTaskListToBottom(page: Page): Promise<void> {
  await page.getByTestId('task-list-scroll').evaluate((element) => {
    element.scrollTop = element.scrollHeight
    element.dispatchEvent(new Event('scroll'))
  })
}

async function pullToRefresh(page: Page): Promise<void> {
  const scroll = page.getByTestId('task-list-scroll')
  await scroll.evaluate((element) => {
    element.scrollTop = 0
  })
  const box = await page.locator('.van-pull-refresh__track').boundingBox()
  if (!box) throw new Error('未找到下拉刷新触控区域')

  const client = await page.context().newCDPSession(page)
  const x = box.x + Math.min(box.width / 2, 120)
  const startY = box.y + 24
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x, y: startY }],
  })
  for (const offset of [36, 72, 108, 144]) {
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

function requestStatuses(requests: string[]): Array<string | null> {
  return requests.map((request) => new URL(request).searchParams.get('status'))
}

for (const viewport of viewports) {
  for (const theme of themes) {
    test(`Task List V2 ${viewport.width}×${viewport.height} ${theme} 保持固定区、独立滚动与零溢出`, async ({
      page,
    }, testInfo) => {
      const consoleErrors = collectConsoleErrors(page)
      await page.setViewportSize(viewport)
      await setThemeBeforeNavigation(page, theme)
      await installMockApi(page)
      await page.goto('/#/tasks')
      await applySafeAreaFixture(page)

      await expect(page.getByTestId('task-card')).toHaveCount(20)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.getByTestId('mobile-global-page-title')).toHaveText(
        '任务',
      )
      await expect(page.getByTestId('task-search')).toBeVisible()
      await expect(page.getByTestId('summary-running')).toHaveText('5')
      await expect(page.getByTestId('summary-pending')).toHaveText('5')
      await expect(page.getByTestId('summary-exception')).toHaveText('10')
      await expect(page.getByTestId('summary-completed')).toHaveText('6')
      await expect(page.getByTestId('mobile-list-context-card')).toContainText(
        '任务26个近7天',
      )

      const geometry = await page.evaluate(() => {
        const card = document.querySelector<HTMLElement>(
          '[data-testid="task-card"]',
        )!
        const artwork = card.querySelector<HTMLElement>(
          '[data-testid="task-card-leading"]',
        )!
        const title = card.querySelector<HTMLElement>(
          '[data-testid="task-card-name"]',
        )!
        const content = card.querySelector<HTMLElement>(
          '.mobile-business-card-frame__content',
        )!
        const titleRow = card.querySelector<HTMLElement>(
          '.mobile-business-card-frame__title',
        )!
        const statusRow = card.querySelector<HTMLElement>(
          '.mobile-business-card-frame__status',
        )!
        const tag = card.querySelector<HTMLElement>('.task-list-card-v2__tag')!
        const scroll = document.querySelector<HTMLElement>(
          '[data-testid="task-list-scroll"]',
        )!
        const list = document.querySelector<HTMLElement>('.task-list')!
        const shellMain = document.querySelector<HTMLElement>(
          '.mobile-app-shell__main',
        )!
        const cardStyle = window.getComputedStyle(card)
        const cardBox = card.getBoundingClientRect()
        const contentBox = content.getBoundingClientRect()
        const artworkBox = artwork.getBoundingClientRect()
        const titleStyle = window.getComputedStyle(title)
        const tagStyle = window.getComputedStyle(tag)
        return {
          cardHeight: cardBox.height,
          cardMinHeight: cardStyle.minHeight,
          cardPadding: [
            cardStyle.paddingTop,
            cardStyle.paddingRight,
            cardStyle.paddingBottom,
            cardStyle.paddingLeft,
          ],
          artwork: [artworkBox.width, artworkBox.height],
          contentWhitespace: [
            Number((contentBox.top - cardBox.top).toFixed(1)),
            Number((cardBox.bottom - contentBox.bottom).toFixed(1)),
          ],
          rhythmGaps: [
            window.getComputedStyle(titleRow).marginBottom,
            window.getComputedStyle(statusRow).marginBottom,
          ],
          tag: {
            height: tag.getBoundingClientRect().height,
            clientHeight: tag.clientHeight,
            scrollHeight: tag.scrollHeight,
            overflow: tagStyle.overflow,
            textOverflow: tagStyle.textOverflow,
            whiteSpace: tagStyle.whiteSpace,
          },
          listGap: window.getComputedStyle(list).rowGap,
          listOverflowY: window.getComputedStyle(scroll).overflowY,
          shellOverflowY: window.getComputedStyle(shellMain).overflowY,
          documentScrollable:
            document.documentElement.scrollHeight > window.innerHeight,
          title: {
            overflow: titleStyle.overflow,
            textOverflow: titleStyle.textOverflow,
            whiteSpace: titleStyle.whiteSpace,
          },
        }
      })
      expect(geometry.cardHeight).toBe(122)
      expect(geometry.cardMinHeight).toBe('122px')
      expect(geometry.cardPadding).toEqual(['15px', '17px', '15px', '16px'])
      expect(geometry.artwork).toEqual([60, 60])
      expect(geometry.contentWhitespace).toEqual([26.1, 26.1])
      expect(geometry.rhythmGaps).toEqual(['5px', '5px'])
      expect(geometry.tag).toEqual({
        height: 26,
        clientHeight: 26,
        scrollHeight: 26,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      })
      expect(geometry.listGap).toBe('14px')
      expect(geometry.listOverflowY).toBe('auto')
      expect(geometry.shellOverflowY).toBe('hidden')
      expect(geometry.documentScrollable).toBe(false)
      expect(geometry.title).toEqual({
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      })

      for (const key of ['running', 'pending', 'exception', 'completed']) {
        const box = await page
          .getByTestId(`summary-metric-${key}`)
          .boundingBox()
        expect(box?.height).toBeGreaterThanOrEqual(44)
      }
      await expect(page.locator('.task-list-card .van-progress')).toHaveCount(0)
      await expect(page.getByText('正在处理第 1 项')).toHaveCount(0)
      await expect(page.locator('body')).not.toContainText('Provider')
      await expectNoHorizontalOverflow(page)
      expect(consoleErrors).toEqual([])

      if (viewport.width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`task-list-v2-390-${theme}.png`),
        })
      }
    })
  }
}

test('状态 Metric、真实搜索与单日期共用正式查询状态', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card')).toHaveCount(20)

  const initialRequest = new URL(state.listRequests[0] ?? '')
  expect(initialRequest.searchParams.has('created_from')).toBe(true)
  expect(initialRequest.searchParams.has('created_to')).toBe(true)

  const beforeRunning = state.listRequests.length
  await page.getByTestId('summary-metric-running').click()
  await expect
    .poll(() => requestStatuses(state.listRequests.slice(beforeRunning)))
    .toContain('running')
  await expect(page.getByTestId('summary-metric-running')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('mobile-list-context-card')).toContainText(
    '运行中5个',
  )

  await page.getByTestId('summary-metric-running').click()
  await expect(page.getByTestId('summary-metric-running')).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  await expect(page.getByTestId('mobile-list-context-card')).toContainText(
    '任务26个',
  )

  const beforeException = state.listRequests.length
  await page.getByTestId('summary-metric-exception').click()
  await expect
    .poll(() =>
      requestStatuses(state.listRequests.slice(beforeException)).sort(),
    )
    .toEqual(['failed', 'lost'])
  await expect(page.getByTestId('mobile-list-context-card')).toContainText(
    '异常任务10个',
  )
  await page.getByTestId('summary-metric-exception').click()

  const searchInput = page.getByTestId('task-search')
  await searchInput.fill('跨境电商')
  await expect
    .poll(() =>
      state.listRequests.some(
        (request) => new URL(request).searchParams.get('search') === '跨境电商',
      ),
    )
    .toBe(true)
  await expect(
    page.getByText('跨境电商多平台每日数据报表汇总与异常核对任务'),
  ).toBeVisible()
  await expect(page.getByTestId('mobile-list-context-card')).toContainText(
    '任务1个',
  )

  await page.getByTestId('mobile-header-menu').click()
  await expect(page.getByTestId('task-date-filter-sheet')).toBeVisible()
  await page.getByTestId('task-date-preset-all-time').click()
  await expect
    .poll(() => {
      const matching = state.listRequests
        .map((request) => new URL(request))
        .filter((url) => url.searchParams.get('search') === '跨境电商')
        .at(-1)
      return matching
        ? [
            matching.searchParams.has('created_from'),
            matching.searchParams.has('created_to'),
          ]
        : null
    })
    .toEqual([false, false])
  await expect(page.getByTestId('task-context-date')).toHaveText('全部')

  await page.getByTestId('mobile-header-menu').click()
  await page.getByTestId('task-custom-date').fill('2026-08-21')
  await page.getByTestId('apply-task-custom-date').click()
  const expectedFrom = new Date(2026, 7, 21).toISOString()
  const expectedTo = new Date(2026, 7, 22).toISOString()
  await expect
    .poll(() => {
      const matching = state.listRequests
        .map((request) => new URL(request))
        .find(
          (url) =>
            url.searchParams.get('created_from') === expectedFrom &&
            url.searchParams.get('created_to') === expectedTo,
        )
      return Boolean(matching)
    })
    .toBe(true)
  await expect(page.getByTestId('task-context-date')).toHaveText('8月21日')
  await expectNoHorizontalOverflow(page)
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('20条以上仅滚动任务列表，并用正式分页继续加载', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card')).toHaveCount(20)

  const before = await page.evaluate(() => {
    const box = (selector: string) =>
      document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
    const scroll = document.querySelector<HTMLElement>(
      '[data-testid="task-list-scroll"]',
    )!
    return {
      headerTop: box('[data-testid="mobile-shell-header"]').top,
      controlsTop: box('[data-testid="task-list-controls"]').top,
      bottomTop: box('[data-testid="mobile-shell-bottom"]').top,
      scrollable: scroll.scrollHeight > scroll.clientHeight,
      documentScrollTop: document.scrollingElement?.scrollTop ?? 0,
    }
  })
  expect(before.scrollable).toBe(true)

  await scrollTaskListToBottom(page)
  await expect(page.getByTestId('task-card')).toHaveCount(26)
  await expect(
    page.getByText('跨境电商多平台每日数据报表汇总与异常核对任务'),
  ).toBeVisible()
  expect(
    state.listRequests.some(
      (request) => new URL(request).searchParams.get('page') === '2',
    ),
  ).toBe(true)

  const after = await page.evaluate(() => {
    const box = (selector: string) =>
      document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
    return {
      headerTop: box('[data-testid="mobile-shell-header"]').top,
      controlsTop: box('[data-testid="task-list-controls"]').top,
      bottomTop: box('[data-testid="mobile-shell-bottom"]').top,
      documentScrollTop: document.scrollingElement?.scrollTop ?? 0,
    }
  })
  expect(after.headerTop).toBeCloseTo(before.headerTop, 1)
  expect(after.controlsTop).toBeCloseTo(before.controlsTop, 1)
  expect(after.bottomTop).toBeCloseTo(before.bottomTop, 1)
  expect(after.documentScrollTop).toBe(0)
  await expectNoHorizontalOverflow(page)
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('初始失败终止Loading并可重试，后台失败保留已有数据', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, {
    initialListDelayMs: 180,
    failInitialListOnce: true,
  })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-loading')).toBeVisible()
  await expect(page.getByTestId('task-error')).toBeVisible()
  await expect(page.getByTestId('task-loading')).toHaveCount(0)
  await expect(page.locator('body')).not.toContainText(
    'DATABASE_OPERATION_FAILED',
  )
  await page
    .getByTestId('task-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('主动刷新失败保留任务并只给出安全摘要', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page, { failRefreshOnce: true })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card')).toHaveCount(20)
  const beforeRefresh = state.listRequests.length

  await pullToRefresh(page)
  await expect
    .poll(() => state.listRequests.length)
    .toBeGreaterThan(beforeRefresh)
  await expect(page.getByText('刷新失败', { exact: true })).toBeVisible()
  await expect(page.getByTestId('task-card')).toHaveCount(20)
  await expect(page.getByTestId('task-error')).toHaveCount(0)
  await expect(page.locator('body')).not.toContainText('仅供测试的技术错误')
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('空态简洁，下一页失败保留已有任务并支持重试', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, { failNextPageOnce: true })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card')).toHaveCount(20)
  await scrollTaskListToBottom(page)
  await expect(page.getByTestId('task-next-page-error')).toBeVisible()
  await expect(page.getByTestId('task-card')).toHaveCount(20)
  await page
    .getByTestId('task-next-page-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByTestId('task-card')).toHaveCount(26)

  await page.unroute('**/api/v1/**')
  await installMockApi(page, { empty: true })
  await page.reload()
  await expect(page.getByTestId('task-empty')).toContainText('近7天无任务')
  await expect(page.getByTestId('task-error')).toHaveCount(0)
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('TaskCard跳转复用正式Task Detail并返回任务列表', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page)
  await page.goto('/#/tasks')

  await page
    .getByRole('button', { name: '查看任务：执行任务 1', exact: true })
    .click()
  await expect(page).toHaveURL(/#\/tasks\/task-1$/)
  await expect(page.getByTestId('task-detail')).toBeVisible()
  await expect(
    page.locator('.van-tabbar-item--active').getByText('任务', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '返回' }).click()
  await expect(page).toHaveURL(/#\/tasks$/)
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})
