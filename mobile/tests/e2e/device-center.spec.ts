import { expect, test, type Page, type Route } from '@playwright/test'

const viewportWidths = [360, 375, 390, 430] as const
const themes = ['light', 'dark'] as const
const safeAreaFixture = {
  top: '19px',
  right: '22px',
  bottom: '23px',
  left: '21px',
} as const

interface MockApiOptions {
  failDevicePage2Once?: boolean
  failDevicePage1AfterSuccessOnce?: boolean
  holdDevicePage1AfterSuccessOnce?: {
    onStarted: () => void
    release: Promise<void>
  }
  failAuxiliary?: boolean
}

interface MockApiState {
  methods: string[]
  deviceListRequests: string[]
  activeTaskRequests: string[]
  providerRequests: string[]
  capabilityRequests: string[]
  taskDetailRequests: string[]
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

async function setThemeBeforeNavigation(
  page: Page,
  theme: (typeof themes)[number],
): Promise<void> {
  await page.addInitScript((mode) => {
    window.localStorage.setItem('control-center.mobile.theme-mode', mode)
  }, theme)
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

async function scrollMainToBottom(page: Page): Promise<void> {
  await page.locator('.mobile-app-shell__main').evaluate((element) => {
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
  if (!box) throw new Error('未找到设备列表下拉刷新触控区域')

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

function makeDevice(index: number) {
  const hasRuntime = index !== 3
  return {
    device_id: `device-${index}`,
    display_name: `设备 ${index}`,
    enabled: index !== 1,
    location: index === 1 ? '华东仓' : null,
    note: index === 1 ? '主执行设备' : null,
    deleted_at: null,
    worker_runtime: hasRuntime
      ? {
          device_id: `device-${index}`,
          worker_version: `1.0.${index}`,
          connection_status: index === 2 ? 'offline' : 'online',
          last_seen_at: '2026-08-26T08:59:00.000Z',
          started_at: '2026-08-26T08:00:00.000Z',
          updated_at: '2026-08-26T08:59:00.000Z',
        }
      : null,
    created_at: '2026-08-01T00:00:00.000Z',
    updated_at: '2026-08-26T08:59:00.000Z',
  }
}

function makeEvent(taskId: string, sequence = 1) {
  return {
    event_id: `event-${taskId}-${sequence}`,
    task_id: taskId,
    seq: sequence,
    event_type: 'status',
    level: 'info',
    message: '正在执行订单同步',
    event_at: '2026-08-26T08:01:00.000Z',
    metadata: {},
    created_at: '2026-08-26T08:01:00.000Z',
  }
}

function makeActiveTask(deviceId: string) {
  const index = Number(deviceId.replace('device-', '')) || 1
  const taskId = `task-active-${index}`
  return {
    task_id: taskId,
    target_device_id: deviceId,
    skill_id: 'sync-orders',
    execution_display_name: index === 2 ? '等待同步订单' : '同步订单',
    status: index === 2 ? 'pending' : 'running',
    started_at: index === 2 ? null : '2026-08-26T08:00:00.000Z',
    created_at: '2026-08-26T07:59:00.000Z',
    latest_event: index === 2 ? null : makeEvent(taskId),
  }
}

function makeTaskListItem() {
  return {
    task_id: 'task-active-1',
    target_device_id: 'device-1',
    device_display_name: '设备 1',
    skill_id: 'sync-orders',
    skill_display_name: '同步订单',
    execution_display_name: '同步订单',
    status: 'running',
    progress: null,
    current_message: '正在执行订单同步',
    started_at: '2026-08-26T08:00:00.000Z',
    finished_at: null,
    created_at: '2026-08-26T07:59:00.000Z',
  }
}

function makeTaskDetail(taskId: string) {
  return {
    task_id: taskId,
    target_device_id: 'device-1',
    shop_ids: ['shop-1'],
    asset_ids: [],
    skill_id: 'sync-orders',
    execution_display_name: '同步订单',
    status: 'running',
    input: {},
    result: null,
    error_code: null,
    error_message: null,
    lease_until: null,
    started_at: '2026-08-26T08:00:00.000Z',
    finished_at: null,
    runtime_events_purged_at: null,
    created_at: '2026-08-26T07:59:00.000Z',
    updated_at: '2026-08-26T08:01:00.000Z',
  }
}

function makeProviderInventory(deviceId: string) {
  return {
    device_id: deviceId,
    provider_code: 'yingdao',
    available: true,
    provider_version: '3.4.5',
    account_display: '测试账号',
    account_type: 'enterprise',
    enterprise_account: true,
    last_discovered_at: '2026-08-26T08:30:00.000Z',
    inventory: {
      provider: 'yingdao',
      available: true,
      status: 'ready',
      status_reason_code: null,
      status_reason: null,
      provider_version: '3.4.5',
      execution_available: true,
      execution_version: '2.0.0',
      execution_unavailable_reason: null,
      logged_in: true,
      account_display: '测试账号',
      account_type: 'enterprise',
      enterprise_account: true,
      user_id: 'provider-user-1',
      applications: [
        {
          app_id: 'app-1',
          app_name: '订单应用',
          version_id: 'version-1',
          updated_at: null,
          app_type: 'rpa',
          group_id: null,
        },
      ],
      discovered_at: '2026-08-26T08:30:00.000Z',
    },
    updated_at: '2026-08-26T08:30:00.000Z',
  }
}

function makeCapabilities(deviceId: string) {
  return [
    ['business-sync', '业务同步', 'business'],
    ['internal-discovery', '内部发现', 'internal'],
    ['unclassified-helper', '待分类能力', null],
  ].map(([skillId, displayName, classification]) => ({
    device_id: deviceId,
    skill_id: skillId,
    display_name: displayName,
    runtime: 'rpa',
    provider: 'yingdao',
    version: '1.0.0',
    classification,
    input_schema: null,
    updated_at: '2026-08-26T08:30:00.000Z',
  }))
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
      request_id: 'request-device-e2e',
      details: null,
    }),
  })
}

async function installMockApi(
  page: Page,
  options: MockApiOptions = {},
): Promise<MockApiState> {
  const state: MockApiState = {
    methods: [],
    deviceListRequests: [],
    activeTaskRequests: [],
    providerRequests: [],
    capabilityRequests: [],
    taskDetailRequests: [],
  }
  let devicePage2Failed = false
  let devicePage1Succeeded = false
  let devicePage1FailedAfterSuccess = false
  let devicePage1HeldAfterSuccess = false

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    const relativePath = url.pathname.replace(/^.*\/api\/v1\//, '')
    state.methods.push(method)

    if (method !== 'GET') {
      return route.fulfill({ status: 405, body: '' })
    }

    const providerMatch = relativePath.match(
      /^devices\/([^/]+)\/provider-inventories$/,
    )
    if (providerMatch) {
      const deviceId = decodeURIComponent(providerMatch[1] ?? '')
      state.providerRequests.push(url.toString())
      return options.failAuxiliary
        ? fulfillApiError(route, '影刀快照加载失败')
        : fulfillJson(route, [makeProviderInventory(deviceId)])
    }

    const capabilityMatch = relativePath.match(
      /^devices\/([^/]+)\/skill-capabilities$/,
    )
    if (capabilityMatch) {
      const deviceId = decodeURIComponent(capabilityMatch[1] ?? '')
      state.capabilityRequests.push(url.toString())
      return options.failAuxiliary
        ? fulfillApiError(route, '技能能力加载失败')
        : fulfillJson(route, makeCapabilities(deviceId))
    }

    const activeTaskMatch = relativePath.match(/^tasks\/active\/([^/]+)$/)
    if (activeTaskMatch) {
      const deviceId = decodeURIComponent(activeTaskMatch[1] ?? '')
      state.activeTaskRequests.push(url.toString())
      if (options.failAuxiliary) {
        return fulfillApiError(route, '当前任务加载失败')
      }
      if (deviceId === 'device-1' || deviceId === 'device-2') {
        return fulfillJson(route, makeActiveTask(deviceId))
      }
      return route.fulfill({ status: 204, body: '' })
    }

    const taskEventsMatch = relativePath.match(/^tasks\/([^/]+)\/events$/)
    if (taskEventsMatch) {
      const taskId = decodeURIComponent(taskEventsMatch[1] ?? '')
      const afterSequence = url.searchParams.get('after_seq')
      const nextAfterSequence = afterSequence ? Number(afterSequence) : 1
      return fulfillJson(route, {
        task_id: taskId,
        after_seq: afterSequence ? Number(afterSequence) : null,
        before_seq: null,
        next_after_seq: nextAfterSequence,
        next_before_seq: null,
        has_more_before: false,
        items: afterSequence ? [] : [makeEvent(taskId)],
      })
    }

    const taskDetailMatch = relativePath.match(/^tasks\/([^/]+)$/)
    if (taskDetailMatch) {
      const taskId = decodeURIComponent(taskDetailMatch[1] ?? '')
      state.taskDetailRequests.push(url.toString())
      return fulfillJson(route, makeTaskDetail(taskId))
    }

    if (relativePath === 'tasks') {
      return fulfillJson(route, {
        items: [makeTaskListItem()],
        total: 1,
        page: Number(url.searchParams.get('page') ?? 1),
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
      const pageSize = Number(url.searchParams.get('page_size') ?? 20)
      if (
        options.holdDevicePage1AfterSuccessOnce &&
        pageNumber === 1 &&
        devicePage1Succeeded &&
        !devicePage1HeldAfterSuccess
      ) {
        devicePage1HeldAfterSuccess = true
        options.holdDevicePage1AfterSuccessOnce.onStarted()
        await options.holdDevicePage1AfterSuccessOnce.release
      }
      if (
        options.failDevicePage1AfterSuccessOnce &&
        pageNumber === 1 &&
        devicePage1Succeeded &&
        !devicePage1FailedAfterSuccess
      ) {
        devicePage1FailedAfterSuccess = true
        return fulfillApiError(route, '设备后台刷新失败')
      }
      if (
        options.failDevicePage2Once &&
        pageNumber === 2 &&
        !devicePage2Failed
      ) {
        devicePage2Failed = true
        return fulfillApiError(route, '下一页设备加载失败')
      }
      if (pageNumber === 1) devicePage1Succeeded = true
      const first = (pageNumber - 1) * pageSize + 1
      const last = Math.min(pageNumber * pageSize, 25)
      return fulfillJson(route, {
        items:
          first > last
            ? []
            : Array.from({ length: last - first + 1 }, (_, index) =>
                makeDevice(first + index),
              ),
        total: 25,
        page: pageNumber,
        page_size: pageSize,
      })
    }

    return fulfillApiError(route, `未处理的测试路径：${relativePath}`)
  })

  return state
}

for (const width of viewportWidths) {
  for (const theme of themes) {
    test(`设备中心 ${width}px ${theme} 主题保持安全区、详情链路与零溢出`, async ({
      page,
    }) => {
      const consoleErrors = collectConsoleErrors(page)
      await page.setViewportSize({ width, height: 844 })
      await setThemeBeforeNavigation(page, theme)
      const state = await installMockApi(page)
      await page.goto('/#/devices')
      await applySafeAreaFixture(page)

      const firstCard = page.getByTestId('device-card').first()
      await expect(firstCard).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(firstCard).toContainText('已停用')
      await expect(firstCard).toContainText('在线')
      await expect(firstCard).toContainText('同步订单')

      const mainButton = firstCard.getByRole('button', {
        name: '查看设备：设备 1',
      })
      expect((await mainButton.boundingBox())?.height).toBeGreaterThanOrEqual(
        44,
      )

      const layout = await page.evaluate(() => {
        const style = (selector: string) => {
          const element = document.querySelector<HTMLElement>(selector)
          if (!element) throw new Error(`未找到布局节点：${selector}`)
          return window.getComputedStyle(element)
        }
        return {
          toolbarLeft: style('.device-center-page__toolbar').paddingLeft,
          toolbarRight: style('.device-center-page__toolbar').paddingRight,
          listLeft: style('.device-list').paddingLeft,
          listRight: style('.device-list').paddingRight,
          footerBottom: style('.mobile-app-shell__bottom').paddingBottom,
          tabbarPosition: style('.van-tabbar').position,
        }
      })
      expect(layout).toEqual({
        toolbarLeft: safeAreaFixture.left,
        toolbarRight: safeAreaFixture.right,
        listLeft: safeAreaFixture.left,
        listRight: safeAreaFixture.right,
        footerBottom: safeAreaFixture.bottom,
        tabbarPosition: 'relative',
      })
      await expectNoHorizontalOverflow(page)

      await mainButton.click()
      await expect(page.getByTestId('device-detail')).toBeVisible()
      await expect(page.getByTestId('provider-inventory')).toContainText('就绪')
      await expect(page.getByTestId('provider-inventory')).toContainText(
        '账号测试账号',
      )
      await expect(page.getByTestId('provider-inventory')).toContainText(
        '企业账号是',
      )
      await expect(page.getByTestId('capability-summary')).toContainText(
        '未分类能力',
      )
      await expect(page.locator('.van-tabbar')).toHaveCount(0)
      const detailSafeArea = await page
        .locator('.app-page')
        .evaluate((element) => {
          const style = window.getComputedStyle(element)
          return { left: style.paddingLeft, right: style.paddingRight }
        })
      expect(detailSafeArea).toEqual({
        left: safeAreaFixture.left,
        right: safeAreaFixture.right,
      })
      await scrollMainToBottom(page)
      await expectNoHorizontalOverflow(page)

      await page.getByRole('button', { name: '查看任务：同步订单' }).click()
      await expect(page).toHaveURL(
        /\/tasks\/task-active-1\?fromDeviceId=device-1$/,
      )
      await expect(page.getByTestId('task-detail')).toBeVisible()
      await expect(page.getByTestId('runtime-events')).toBeVisible()
      await expectNoHorizontalOverflow(page)
      expect(state.taskDetailRequests).toHaveLength(1)

      await page.locator('.van-nav-bar__left').click()
      await expect(page).toHaveURL(/\/devices\/device-1$/)
      await expect(page.getByTestId('device-detail')).toBeVisible()
      expect(state.methods.every((method) => method === 'GET')).toBe(true)
      expect(consoleErrors).toEqual([])
    })
  }
}

test('设备列表按正式 20 条分页、下拉刷新并保持底部任务/设备导航', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  await page.goto('/#/devices')

  await expect(page.getByTestId('device-card').first()).toBeVisible()
  const firstRequest = new URL(state.deviceListRequests[0] ?? '')
  expect(firstRequest.searchParams.get('page')).toBe('1')
  expect(firstRequest.searchParams.get('page_size')).toBe('20')
  expect([...firstRequest.searchParams.keys()].sort()).toEqual([
    'page',
    'page_size',
  ])

  await scrollMainToBottom(page)
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()
  expect(
    state.deviceListRequests.some((request) => {
      const params = new URL(request).searchParams
      return params.get('page') === '2' && params.get('page_size') === '20'
    }),
  ).toBe(true)

  const requestCountBeforeRefresh = state.deviceListRequests.length
  await pullToRefresh(page)
  await expect
    .poll(() => state.deviceListRequests.length)
    .toBeGreaterThan(requestCountBeforeRefresh)
  expect(
    state.deviceListRequests
      .slice(requestCountBeforeRefresh)
      .some((request) => new URL(request).searchParams.get('page') === '1'),
  ).toBe(true)
  expect(
    state.deviceListRequests
      .slice(requestCountBeforeRefresh)
      .every((request) => new URL(request).searchParams.get('page') === '1'),
  ).toBe(true)
  await expect(page.getByText('设备 25', { exact: true })).toHaveCount(0)

  await page.getByRole('tab', { name: /任务$/ }).click()
  await expect(page.getByTestId('task-card')).toBeVisible()
  await page.getByRole('tab', { name: /设备$/ }).click()
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  expect(consoleErrors).toEqual([])
})

test('设备后台刷新失败保留旧卡片并遵守左右安全区', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, { failDevicePage1AfterSuccessOnce: true })
  await page.goto('/#/devices')
  await applySafeAreaFixture(page)
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await scrollMainToBottom(page)
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()

  await pullToRefresh(page)
  const backgroundError = page.getByTestId('device-background-error')
  await expect(backgroundError).toBeVisible()
  await expect(backgroundError).toContainText('设备后台刷新失败')
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()

  const padding = await backgroundError.evaluate((element) => {
    const style = window.getComputedStyle(element)
    return { left: style.paddingLeft, right: style.paddingRight }
  })
  expect(padding).toEqual({
    left: safeAreaFixture.left,
    right: safeAreaFixture.right,
  })
  await expectNoHorizontalOverflow(page)
})

test('手动刷新跨过定时边界时暂停后台分页刷新', async ({ page }) => {
  let notifyRefreshStarted: () => void = () => undefined
  const refreshStarted = new Promise<void>((resolve) => {
    notifyRefreshStarted = resolve
  })
  let releaseRefresh: () => void = () => undefined
  const refreshRelease = new Promise<void>((resolve) => {
    releaseRefresh = resolve
  })

  await page.clock.install({ time: new Date('2026-08-26T09:00:00.000Z') })
  const state = await installMockApi(page, {
    holdDevicePage1AfterSuccessOnce: {
      onStarted: notifyRefreshStarted,
      release: refreshRelease,
    },
  })
  await page.goto('/#/devices')
  await scrollMainToBottom(page)
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()

  const requestCountBeforeRefresh = state.deviceListRequests.length
  await pullToRefresh(page)
  await refreshStarted
  await page.clock.fastForward(16_000)
  await new Promise((resolve) => setTimeout(resolve, 200))

  expect(
    state.deviceListRequests
      .slice(requestCountBeforeRefresh)
      .map((request) => new URL(request).searchParams.get('page')),
  ).toEqual(['1'])

  releaseRefresh()
  await page.clock.resume()
  await expect(page.getByText('设备 25', { exact: true })).toHaveCount(0)
})

test('设备下一页失败只在尾部提示并可显式重试', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installMockApi(page, { failDevicePage2Once: true })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card').first()).toBeVisible()

  await scrollMainToBottom(page)
  await expect(page.getByTestId('device-list-next-page-error')).toBeVisible()
  await expect(page.getByTestId('device-background-error')).toHaveCount(0)
  await page
    .getByTestId('device-list-next-page-error')
    .getByRole('button', { name: '重试加载更多' })
    .click()
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()
})

test('设备详情成功时三类辅助失败各自展示且不覆盖主数据', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  const state = await installMockApi(page, { failAuxiliary: true })
  await page.goto('/#/devices/device-1')

  await expect(page.getByTestId('device-detail')).toBeVisible()
  await expect(page.getByText('设备 1', { exact: true })).toBeVisible()
  await expect(page.getByText('当前任务加载失败')).toBeVisible()
  await expect(page.getByText('影刀快照加载失败')).toBeVisible()
  await expect(page.getByText('技能能力加载失败')).toBeVisible()
  expect(state.activeTaskRequests.length).toBeGreaterThan(0)
  expect(state.providerRequests).toHaveLength(1)
  expect(state.capabilityRequests).toHaveLength(1)
  await expectNoHorizontalOverflow(page)
})

test('未上报 Runtime 与离线是不同事实', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page)

  await page.goto('/#/devices/device-3')
  await expect(page.getByTestId('runtime-unreported')).toContainText(
    '未上报运行端信息',
  )
  await expect(page.getByTestId('device-detail')).toContainText('未上报')
  await expect(page.getByTestId('device-detail')).not.toContainText('离线')

  await page.goto('/#/devices/device-2')
  await expect(page.getByTestId('device-detail')).toContainText('离线')
  await expect(page.getByTestId('device-detail')).toContainText('已启用')
})
