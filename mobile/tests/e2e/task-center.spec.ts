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
  taskTotal?: number
  failTaskPage1AfterSuccessOnce?: boolean
  holdTaskPage1AfterSuccessOnce?: {
    onStarted: () => void
    release: Promise<void>
  }
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

  await expect
    .poll(() =>
      page.evaluate(() => {
        const style = window.getComputedStyle(document.documentElement)
        return {
          top: style.getPropertyValue('--safe-area-top').trim(),
          right: style.getPropertyValue('--safe-area-right').trim(),
          bottom: style.getPropertyValue('--safe-area-bottom').trim(),
          left: style.getPropertyValue('--safe-area-left').trim(),
        }
      }),
    )
    .toEqual(safeAreaFixture)
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

async function countCardsInsideListViewport(
  page: Page,
  selector: string,
): Promise<number> {
  return page.locator(selector).evaluateAll((elements) => {
    const main = document
      .querySelector<HTMLElement>('[data-testid="task-list-scroll"]')
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
  const now = Date.now()
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
    started_at:
      status === 'pending'
        ? null
        : status === 'running'
          ? new Date(now - 90_000).toISOString()
          : '2026-08-26T01:00:00.000Z',
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
  let taskPage1Succeeded = false
  let taskPage1FailedAfterSuccess = false
  let taskPage1HeldAfterSuccess = false
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

      if (
        options.holdTaskPage1AfterSuccessOnce &&
        pageNumber === 1 &&
        taskPage1Succeeded &&
        !taskPage1HeldAfterSuccess
      ) {
        taskPage1HeldAfterSuccess = true
        options.holdTaskPage1AfterSuccessOnce.onStarted()
        await options.holdTaskPage1AfterSuccessOnce.release
      }
      if (
        options.failTaskPage1AfterSuccessOnce &&
        pageNumber === 1 &&
        taskPage1Succeeded &&
        !taskPage1FailedAfterSuccess
      ) {
        taskPage1FailedAfterSuccess = true
        return fulfillApiError(route, '任务刷新失败')
      }

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
      let filtered =
        options.taskTotal === undefined
          ? taskItems
          : Array.from({ length: options.taskTotal }, (_, index) =>
              makeTaskListItem(index + 1),
            )
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
      if (pageNumber === 1) taskPage1Succeeded = true
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

async function scrollTaskListToBottom(page: Page): Promise<void> {
  await page.getByTestId('task-list-scroll').evaluate((element) => {
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
  const main = page.getByTestId('task-list-scroll')
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
      await expect(page.locator('.task-list-card .van-progress')).toHaveCount(0)
      await expect(page.getByText('1 / 30', { exact: true })).toHaveCount(0)
      await expect(
        page.getByText('正在处理第 1 项', { exact: true }),
      ).toHaveCount(0)
      expect(
        await countCardsInsideListViewport(page, '.task-list__item'),
      ).toBeGreaterThanOrEqual(4)

      const titleStyle = await page
        .getByTestId('task-card-name')
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

      const firstTaskCard = page.getByTestId('task-card').first()
      const cardAnatomy = await firstTaskCard.evaluate((card) => {
        const box = (testId: string) =>
          card
            .querySelector<HTMLElement>(`[data-testid="${testId}"]`)!
            .getBoundingClientRect()
        const root = card.getBoundingClientRect()
        const leading = box('task-card-leading')
        const content = box('task-card-name')
        const chevron = box('task-card-chevron')
        const leadingStyle = window.getComputedStyle(
          card.querySelector<HTMLElement>('[data-testid="task-card-leading"]')!,
        )
        const chevronStyle = window.getComputedStyle(
          card.querySelector<HTMLElement>('[data-testid="task-card-chevron"]')!,
        )
        return {
          leadingLeft: leading.left,
          leadingRight: leading.right,
          leadingWidth: leading.width,
          leadingIconSize: Number.parseFloat(leadingStyle.fontSize),
          contentLeft: content.left,
          contentRight: content.right,
          chevronLeft: chevron.left,
          chevronRight: chevron.right,
          chevronWidth: chevron.width,
          chevronIconSize: Number.parseFloat(chevronStyle.fontSize),
          chevronCenterDelta: Math.abs(
            chevron.top + chevron.height / 2 - (root.top + root.height / 2),
          ),
        }
      })
      expect(cardAnatomy.leadingLeft).toBeLessThan(cardAnatomy.contentLeft)
      expect(cardAnatomy.leadingRight).toBeLessThanOrEqual(
        cardAnatomy.contentLeft,
      )
      expect(cardAnatomy.leadingWidth).toBe(72)
      expect(cardAnatomy.leadingIconSize).toBe(56)
      expect(cardAnatomy.contentRight).toBeLessThanOrEqual(
        cardAnatomy.chevronLeft,
      )
      expect(cardAnatomy.chevronWidth).toBe(22)
      expect(cardAnatomy.chevronIconSize).toBe(16)
      expect(cardAnatomy.chevronRight).toBeGreaterThan(cardAnatomy.contentRight)
      expect(cardAnatomy.chevronCenterDelta).toBeLessThanOrEqual(1)

      const cardSurface = await page
        .locator('.task-list-card')
        .first()
        .evaluate((element) => {
          const probe = document.createElement('span')
          probe.style.color = 'var(--bg-surface-raised)'
          document.body.append(probe)
          const expectedBackground = window.getComputedStyle(probe).color
          probe.remove()
          const shadowProbe = document.createElement('span')
          shadowProbe.style.boxShadow =
            'var(--appearance-border-surface), var(--shadow-card)'
          document.body.append(shadowProbe)
          const expectedShadow = window.getComputedStyle(shadowProbe).boxShadow
          shadowProbe.remove()
          const style = window.getComputedStyle(element)
          return {
            background: style.backgroundColor,
            shadow: style.boxShadow,
            expectedBackground,
            expectedShadow,
          }
        })
      expect(cardSurface).toEqual({
        background: cardSurface.expectedBackground,
        shadow: cardSurface.expectedShadow,
        expectedBackground: cardSurface.expectedBackground,
        expectedShadow: cardSurface.expectedShadow,
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
        const toolbar = document
          .querySelector<HTMLElement>('.mobile-list-toolbar')
          ?.getBoundingClientRect()
        const toolbarChildren = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.mobile-list-toolbar__identity, .mobile-list-toolbar__actions',
          ),
        ).map((element) => element.getBoundingClientRect())
        const selector = document
          .querySelector<HTMLElement>('[data-testid="mobile-list-selector"]')!
          .getBoundingClientRect()
        const filter = document
          .querySelector<HTMLElement>('[data-testid="mobile-list-filter"]')!
          .getBoundingClientRect()
        return {
          headerHeight: style('.mobile-global-header').height,
          toolbarLeft: style('.mobile-list-toolbar').paddingLeft,
          toolbarRight: style('.mobile-list-toolbar').paddingRight,
          toolbarHeight: style('.mobile-list-toolbar').height,
          selectorWidth: selector.width,
          selectorHeight: style('[data-testid="mobile-list-selector"]').height,
          selectorVisualHeight: style(
            '[data-testid="mobile-list-selector"] .mobile-list-toolbar__control',
          ).height,
          filterWidth: filter.width,
          filterHeight: style('[data-testid="mobile-list-filter"]').height,
          filterVisualHeight: style(
            '[data-testid="mobile-list-filter"] .mobile-list-toolbar__control',
          ).height,
          toolbarSingleRow:
            toolbarChildren.length === 2 &&
            toolbarChildren.every(
              (child) =>
                toolbar &&
                child.top >= toolbar.top &&
                child.bottom <= toolbar.bottom,
            ),
          selectorBeforeFilter: selector.right <= filter.left + 0.5,
          toolbarBorderWidth: style('.mobile-list-toolbar').borderWidth,
          toolbarBorderRadius: style('.mobile-list-toolbar').borderRadius,
          toolbarBoxShadow: style('.mobile-list-toolbar').boxShadow,
          listLeft: style('.task-list').paddingLeft,
          listRight: style('.task-list').paddingRight,
          listOverflowY: style('[data-testid="task-list-scroll"]').overflowY,
          listScrollbarWidth: style('[data-testid="task-list-scroll"]')
            .scrollbarWidth,
          shellMainOverflowY: style('.mobile-app-shell__main').overflowY,
          footerBottom: style('.mobile-app-shell__bottom').paddingBottom,
          bottomNavHeight: style('.van-tabbar').height,
          tabbarPosition: style('.van-tabbar').position,
          mainBottom: main?.bottom ?? 0,
          footerTop: footer?.top ?? 0,
          tabbarBottom: tabbar?.bottom ?? 0,
          footerBottomEdge: footer?.bottom ?? 0,
        }
      })
      expect(layout).toMatchObject({
        headerHeight: '52px',
        toolbarLeft: safeAreaFixture.left,
        toolbarRight: safeAreaFixture.right,
        toolbarHeight: '46px',
        selectorHeight: '45px',
        selectorVisualHeight: '26px',
        filterHeight: '45px',
        filterVisualHeight: '26px',
        toolbarSingleRow: true,
        selectorBeforeFilter: true,
        toolbarBorderWidth: '0px',
        toolbarBorderRadius: '0px',
        toolbarBoxShadow: 'none',
        listLeft: safeAreaFixture.left,
        listRight: safeAreaFixture.right,
        listOverflowY: 'auto',
        listScrollbarWidth: 'none',
        shellMainOverflowY: 'hidden',
        footerBottom: safeAreaFixture.bottom,
        bottomNavHeight: '58px',
      })
      expect(layout.selectorWidth).toBeGreaterThanOrEqual(44)
      expect(layout.filterWidth).toBeGreaterThanOrEqual(44)
      expect(layout.tabbarPosition).not.toBe('fixed')
      expect(layout.mainBottom).toBeLessThanOrEqual(layout.footerTop + 1)
      expect(layout.tabbarBottom).toBeLessThanOrEqual(
        layout.footerBottomEdge - 23 + 1,
      )

      await page.getByTestId('mobile-list-filter').click()
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
      await page.getByTestId('device-filter').click()
      const deviceBack = page.getByRole('button', {
        name: '返回',
        exact: true,
      })
      await expect(deviceBack).toBeVisible()
      await deviceBack.focus()
      await expect(deviceBack).toBeFocused()
      const deviceBackHeight = (await deviceBack.boundingBox())?.height
      expect(deviceBackHeight).toBeDefined()
      expect(Math.round(deviceBackHeight!)).toBeGreaterThanOrEqual(44)
      await deviceBack.press(theme === 'light' ? 'Enter' : 'Space')
      await expect(
        page.locator('.task-filter-sheet__device-popup'),
      ).toBeHidden()
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
      await expect(page.getByTestId('mobile-detail-header')).toHaveCSS(
        'height',
        '51px',
      )
      await expect(page.getByTestId('runtime-events')).toBeVisible()
      const detailFlow = await page.evaluate(() => {
        const currentMessage = document.querySelector<HTMLElement>(
          '[data-testid="detail-current-message"]',
        )
        const firstEvent = document.querySelector<HTMLElement>(
          '[data-testid="runtime-events"] li',
        )
        const meta =
          firstEvent?.querySelector<HTMLElement>('.runtime-log__meta')
        const message = firstEvent?.querySelector<HTMLElement>(
          '.runtime-log__message',
        )
        if (!currentMessage || !meta || !message) {
          throw new Error('任务详情视觉节点不完整')
        }
        const currentStyle = window.getComputedStyle(currentMessage)
        const metaBox = meta.getBoundingClientRect()
        const messageBox = message.getBoundingClientRect()
        return {
          currentWhiteSpace: currentStyle.whiteSpace,
          currentOverflowWrap: currentStyle.overflowWrap,
          messageBelowMeta: messageBox.top >= metaBox.bottom,
        }
      })
      expect(detailFlow).toEqual({
        currentWhiteSpace: 'pre-wrap',
        currentOverflowWrap: 'anywhere',
        messageBelowMeta: true,
      })
      const detailSurfaces = await page.evaluate(() => {
        const selectors = [
          '.task-detail-page__summary',
          '.task-detail-page__core',
          '.runtime-log',
        ]
        const resolveColor = (token: string) => {
          const probe = document.createElement('span')
          probe.style.color = `var(${token})`
          document.body.append(probe)
          const color = window.getComputedStyle(probe).color
          probe.remove()
          return color
        }
        const resolveShadow = (value: string) => {
          const probe = document.createElement('span')
          probe.style.boxShadow = value
          document.body.append(probe)
          const shadow = window.getComputedStyle(probe).boxShadow
          probe.remove()
          return shadow
        }
        return {
          expectedCardBackground: resolveColor('--bg-surface-raised'),
          expectedSectionBackground: resolveColor('--bg-surface'),
          expectedPanelShadow: resolveShadow(
            'var(--appearance-border-surface)',
          ),
          expectedCardShadow: resolveShadow(
            'var(--appearance-border-surface), var(--shadow-card)',
          ),
          backgrounds: selectors.map(
            (selector) =>
              window.getComputedStyle(
                document.querySelector<HTMLElement>(selector)!,
              ).backgroundColor,
          ),
          shadows: selectors.map(
            (selector) =>
              window.getComputedStyle(
                document.querySelector<HTMLElement>(selector)!,
              ).boxShadow,
          ),
        }
      })
      expect(detailSurfaces.backgrounds).toEqual([
        detailSurfaces.expectedCardBackground,
        detailSurfaces.expectedSectionBackground,
        detailSurfaces.expectedSectionBackground,
      ])
      expect(detailSurfaces.shadows).toEqual([
        detailSurfaces.expectedCardShadow,
        detailSurfaces.expectedPanelShadow,
        detailSurfaces.expectedPanelShadow,
      ])
      const moreInformation = page.getByTestId('task-more-information')
      await expect(
        moreInformation.locator('.van-collapse-item__content'),
      ).toBeHidden()
      if (width === 390 && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath('task-detail-390-light.png'),
        })
      }
      await expect(page.locator('.van-tabbar-item')).toHaveText([
        '设备',
        '任务',
        '计划',
        '店铺',
        '我的',
      ])
      await expect(
        page.locator('.van-tabbar-item--active').getByText('任务', {
          exact: true,
        }),
      ).toBeVisible()
      await expectNoHorizontalOverflow(page)
      expect(consoleErrors).toEqual([])
    })
  }
}

test('360px 工具行单行展示 54 个任务与紧凑可触操作', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 360, height: 844 })
  await setThemeBeforeNavigation(page, 'light')
  await installMockApi(page, { taskTotal: 54 })
  await page.goto('/#/tasks')

  const toolbar = page.getByTestId('mobile-list-toolbar')
  await expect(toolbar).toContainText('任务54个')
  await expect(page.getByTestId('mobile-list-selector')).toContainText('全部')
  await expect(page.getByTestId('mobile-list-filter')).toContainText('筛选')
  const geometry = await toolbar.evaluate((element) => {
    const toolbarBox = element.getBoundingClientRect()
    const groups = Array.from(
      element.querySelectorAll<HTMLElement>(
        '.mobile-list-toolbar__identity, .mobile-list-toolbar__actions',
      ),
    ).map((group) => group.getBoundingClientRect())
    const controls = Array.from(
      element.querySelectorAll<HTMLElement>(
        '[data-testid="mobile-list-selector"], [data-testid="mobile-list-filter"]',
      ),
    ).map((control) => control.getBoundingClientRect())
    return {
      singleRow: groups.every(
        (group) =>
          group.top >= toolbarBox.top && group.bottom <= toolbarBox.bottom,
      ),
      touchTargets: controls.map((control) => control.height),
    }
  })
  expect(geometry.singleRow).toBe(true)
  expect(geometry.touchTargets.every((height) => height >= 44)).toBe(true)
  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})

test('20 条以上任务只滚动 Card List，单行 Toolbar 与 Shell 保持原位', async ({
  page,
}, testInfo) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await setThemeBeforeNavigation(page, 'light')
  await installMockApi(page)
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await expect(page.getByTestId('task-card')).toHaveCount(20)

  const readLayout = () =>
    page.evaluate(() => {
      const top = (selector: string) =>
        document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
          .top
      const scroll = document.querySelector<HTMLElement>(
        '[data-testid="task-list-scroll"]',
      )!
      const toolbar = document
        .querySelector<HTMLElement>('.mobile-list-toolbar')!
        .getBoundingClientRect()
      const controls = Array.from(
        document.querySelectorAll<HTMLElement>(
          '.mobile-list-toolbar__identity, .mobile-list-toolbar__actions',
        ),
      ).map((element) => element.getBoundingClientRect())
      return {
        headerTop: top('[data-testid="mobile-shell-header"]'),
        toolbarTop: toolbar.top,
        bottomTop: top('[data-testid="mobile-shell-bottom"]'),
        firstCardTop: top('[data-testid="task-card"]'),
        toolbarSingleRow: controls.every(
          (control) =>
            control.top >= toolbar.top && control.bottom <= toolbar.bottom,
        ),
        listScrollTop: scroll.scrollTop,
        listScrollable: scroll.scrollHeight > scroll.clientHeight,
        scrollbarWidth: window.getComputedStyle(scroll).scrollbarWidth,
        shellScrollTop: document.querySelector<HTMLElement>(
          '.mobile-app-shell__main',
        )!.scrollTop,
        documentScrollTop: document.scrollingElement?.scrollTop ?? 0,
        documentScrollable:
          (document.scrollingElement?.scrollHeight ?? 0) >
          (document.scrollingElement?.clientHeight ?? 0),
      }
    })

  const before = await readLayout()
  expect(before.toolbarSingleRow).toBe(true)
  expect(before.listScrollable).toBe(true)
  expect(before.scrollbarWidth).toBe('none')
  expect(before.documentScrollable).toBe(false)
  const taskScroll = page.getByTestId('task-list-scroll')
  await taskScroll.focus()
  await page.keyboard.press('PageDown')
  await expect
    .poll(() => taskScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  await page.waitForTimeout(500)
  await taskScroll.evaluate((element) => {
    element.scrollTop = 0
    element.blur()
  })
  await expect
    .poll(() => taskScroll.evaluate((element) => element.scrollTop))
    .toBe(0)
  await page.screenshot({
    path: testInfo.outputPath('layout-task-390-light-top.png'),
  })
  await taskScroll.evaluate((element) => {
    element.scrollTop = 320
    element.dispatchEvent(new Event('scroll'))
  })
  await expect
    .poll(() => taskScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  const after = await readLayout()

  expect(after.headerTop).toBeCloseTo(before.headerTop, 1)
  expect(after.toolbarTop).toBeCloseTo(before.toolbarTop, 1)
  expect(after.bottomTop).toBeCloseTo(before.bottomTop, 1)
  expect(after.firstCardTop).toBeLessThan(before.firstCardTop)
  expect(after.toolbarSingleRow).toBe(true)
  expect(after.shellScrollTop).toBe(0)
  expect(after.documentScrollTop).toBe(0)
  await page.screenshot({
    path: testInfo.outputPath('layout-task-390-light-mid.png'),
  })

  await scrollTaskListToBottom(page)
  await expect(page.getByText('专项同步').first()).toBeVisible()
  await expect(page.getByTestId('mobile-shell-header')).toBeVisible()
  await expect(page.getByTestId('mobile-list-toolbar')).toBeVisible()
  await expect(page.getByTestId('mobile-shell-bottom')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})

test('筛选、完整分页、下拉刷新、终态日志补齐与返回形成闭环', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks')
  await applySafeAreaFixture(page)

  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await page.getByTestId('mobile-list-selector').click()
  expect(
    await page.locator('.van-action-sheet__item').allTextContents(),
  ).toEqual(['全部', '待执行', '执行中', '成功', '失败', '已丢失'])
  const initialRequest = new URL(state.taskListRequests[0] ?? '')
  expect(initialRequest.searchParams.has('created_from')).toBe(true)
  expect(initialRequest.searchParams.has('created_to')).toBe(true)

  await scrollTaskListToBottom(page)
  await expect(page.getByText('专项同步').first()).toBeVisible()

  await page
    .locator('.van-action-sheet__item')
    .filter({ hasText: /^失败$/ })
    .click()
  await expect
    .poll(() => {
      const request = state.taskListRequests.at(-1)
      return request ? new URL(request).searchParams.get('status') : null
    })
    .toBe('failed')
  await expect(page.getByText('失败').last()).toBeVisible()
  await page.getByTestId('mobile-list-selector').click()
  await page
    .locator('.van-action-sheet__item')
    .filter({ hasText: /^全部$/ })
    .click()

  await page.getByTestId('mobile-list-filter').click()
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

  await page.getByTestId('mobile-list-filter').click()
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
  await page
    .getByTestId('task-more-information')
    .locator('.van-collapse-item__title')
    .click()
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

  await page
    .getByTestId('mobile-detail-header')
    .getByRole('button', { name: '返回' })
    .click()
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
    await page.getByTestId('mobile-list-filter').click()
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

  await page.getByTestId('mobile-list-filter').click()
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

  await page.getByTestId('mobile-list-filter').click()
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

  await scrollTaskListToBottom(page)
  await expect(page.getByTestId('task-next-page-error')).toBeVisible()
  await expect(page.getByTestId('background-error')).toHaveCount(0)
  await page
    .getByTestId('task-next-page-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByText('专项同步').first()).toBeVisible()

  await page.getByTestId('mobile-list-filter').click()
  await page.getByTestId('device-filter').click()
  const devicePopup = page.locator('.task-filter-sheet__device-popup')
  await expect(devicePopup.getByText('设备 1', { exact: true })).toBeVisible()
  await scrollDevicePopupToBottom(page)
  await expect(page.getByTestId('device-next-page-error')).toBeVisible()
  await page
    .getByTestId('device-next-page-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(devicePopup.getByText('设备 101', { exact: true })).toBeVisible()
})

test('成功空缓存后台失败仍展示空态且不解释刷新机制', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const state = await installMockApi(page, { emptyThenBackgroundFailure: true })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-empty')).toBeVisible()

  await expect
    .poll(() => state.taskListRequests.length, { timeout: 7_000 })
    .toBeGreaterThan(1)
  await expect(page.getByTestId('background-error')).toHaveCount(0)
  await expect(page.getByTestId('task-empty')).toBeVisible()
  await expect(page.getByTestId('task-error')).toHaveCount(0)
  await expect(page.getByTestId('mobile-shell-header')).toBeVisible()
  await expect(page.getByTestId('mobile-list-toolbar')).toBeVisible()
  await expect(page.getByTestId('mobile-shell-bottom')).toBeVisible()
  expect(
    await page
      .getByTestId('task-empty')
      .evaluate(
        (element) =>
          element.closest('[data-testid="task-list-scroll"]') !== null,
      ),
  ).toBe(true)
})

test('任务主动刷新失败保留多页缓存并仅提示刷新失败', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page, {
    taskTotal: 45,
    failTaskPage1AfterSuccessOnce: true,
  })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await scrollTaskListToBottom(page)
  await expect(page.getByText('执行任务 21', { exact: true })).toHaveCount(1)

  const requestCountBeforeRefresh = state.taskListRequests.length
  await pullToRefresh(page)

  await expect(page.getByText('刷新失败', { exact: true })).toBeVisible()
  await expect(page.getByText('执行任务 21', { exact: true })).toHaveCount(1)
  expect(
    state.taskListRequests
      .slice(requestCountBeforeRefresh)
      .map((request) => new URL(request).searchParams.get('page')),
  ).toEqual(['1'])
  await expect(page.locator('body')).not.toContainText('任务刷新失败')
})

test('任务刷新进行中阻止下一页并在成功后收敛为第一页', async ({ page }) => {
  let notifyRefreshStarted: () => void = () => undefined
  const refreshStarted = new Promise<void>((resolve) => {
    notifyRefreshStarted = resolve
  })
  let releaseRefresh: () => void = () => undefined
  const refreshRelease = new Promise<void>((resolve) => {
    releaseRefresh = resolve
  })
  const state = await installMockApi(page, {
    taskTotal: 45,
    holdTaskPage1AfterSuccessOnce: {
      onStarted: notifyRefreshStarted,
      release: refreshRelease,
    },
  })
  await page.goto('/#/tasks')
  await expect(page.getByTestId('task-card').first()).toBeVisible()
  await scrollTaskListToBottom(page)
  await expect(page.getByText('执行任务 21', { exact: true })).toHaveCount(1)

  const requestCountBeforeRefresh = state.taskListRequests.length
  await pullToRefresh(page)
  await refreshStarted
  await scrollTaskListToBottom(page)
  await page.waitForTimeout(200)

  expect(
    state.taskListRequests
      .slice(requestCountBeforeRefresh)
      .map((request) => new URL(request).searchParams.get('page')),
  ).toEqual(['1'])
  await expect(page.getByText('执行任务 21', { exact: true })).toHaveCount(1)

  releaseRefresh()
  await expect(page.getByText('执行任务 21', { exact: true })).toHaveCount(0)
})

test('非终态详情持续发送 after_seq 增量请求', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/tasks/task-1')
  await expect(page.getByTestId('runtime-events')).toBeVisible()
  const duration = page.getByTestId('task-detail-duration')
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
