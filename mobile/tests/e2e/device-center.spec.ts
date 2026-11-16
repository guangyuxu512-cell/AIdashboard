import { expect, test, type Page, type Route } from '@playwright/test'

import { createMobileAuthApiFixture } from './auth-api-fixture'

const viewportWidths = [360, 375, 390, 430] as const
const themes = ['light', 'dark'] as const
const safeAreaFixture = {
  top: '19px',
  right: '22px',
  bottom: '23px',
  left: '21px',
} as const

interface MockApiOptions {
  deviceTotal?: number
  failDevicePage1Once?: boolean
  failDevicePage2Once?: boolean
  failDevicePage1AfterSuccessOnce?: boolean
  holdDevicePage1AfterSuccessOnce?: {
    onStarted: () => void
    release: Promise<void>
  }
  holdDevicePage2Once?: {
    onStarted: () => void
    release: Promise<void>
  }
  failAuxiliary?: boolean
  holdActiveTaskOnce?: {
    deviceId: string
    onStarted: () => void
    release: Promise<void>
  }
  failActiveAfterSuccessDeviceId?: string
  failActiveOnceDeviceId?: string
  clearActiveAfterSuccessDeviceId?: string
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

async function countCardsInsideListViewport(
  page: Page,
  selector: string,
): Promise<number> {
  return page.locator(selector).evaluateAll((elements) => {
    const main = document
      .querySelector<HTMLElement>('[data-testid="device-list-scroll"]')
      ?.getBoundingClientRect()
    if (!main) return 0
    return elements.filter((element) => {
      const card = element.getBoundingClientRect()
      return card.top >= main.top && card.bottom <= main.bottom
    }).length
  })
}

async function isCardVisibleInsideListViewport(
  page: Page,
  selector: string,
  index: number,
): Promise<boolean> {
  return page
    .locator(selector)
    .nth(index)
    .evaluate((element) => {
      const main = document
        .querySelector<HTMLElement>('[data-testid="device-list-scroll"]')
        ?.getBoundingClientRect()
      if (!main) return false
      const card = element.getBoundingClientRect()
      return card.top < main.bottom && card.bottom > main.top
    })
}

async function scrollDeviceListToBottom(page: Page): Promise<void> {
  await page.getByTestId('device-list-scroll').evaluate((element) => {
    element.scrollTop = element.scrollHeight
    element.dispatchEvent(new Event('scroll'))
  })
}

async function scrollDetailToBottom(page: Page): Promise<void> {
  await page.locator('.app-page').evaluate((element) => {
    element.scrollTop = element.scrollHeight
    element.dispatchEvent(new Event('scroll'))
  })
}

async function pullToRefresh(page: Page): Promise<void> {
  const main = page.getByTestId('device-list-scroll')
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

async function pullBelowRefreshThreshold(page: Page): Promise<void> {
  const main = page.getByTestId('device-list-scroll')
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
  for (const offset of [8, 16, 24]) {
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x, y: startY + offset }],
    })
  }
  await expect(page.getByTestId('mobile-pull-refresh-pulling')).toBeVisible()
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
    enabled: index !== 4,
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
    provider_version: '6.3.6',
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
      provider_version: '6.3.6',
      execution_available: true,
      execution_version: '6.3.6',
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
    runtime: classification === 'business' ? 'python' : 'rpa',
    provider: classification === 'business' ? null : 'yingdao',
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
  const auth = createMobileAuthApiFixture()
  const state: MockApiState = {
    methods: [],
    deviceListRequests: [],
    activeTaskRequests: [],
    providerRequests: [],
    capabilityRequests: [],
    taskDetailRequests: [],
  }
  let devicePage2Failed = false
  let devicePage1InitialFailed = false
  let devicePage1Succeeded = false
  let devicePage1FailedAfterSuccess = false
  let devicePage1HeldAfterSuccess = false
  let devicePage2Held = false
  const activeTaskRequestCounts = new Map<string, number>()

  await page.route('**/api/v1/**', async (route) => {
    if (await auth.handle(route)) return
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
      const activeRequestCount =
        (activeTaskRequestCounts.get(deviceId) ?? 0) + 1
      activeTaskRequestCounts.set(deviceId, activeRequestCount)
      if (options.failAuxiliary) {
        return fulfillApiError(route, '当前任务加载失败')
      }
      if (
        options.failActiveOnceDeviceId === deviceId &&
        activeRequestCount === 1
      ) {
        return fulfillApiError(route, '当前任务加载失败')
      }
      if (
        options.holdActiveTaskOnce?.deviceId === deviceId &&
        activeRequestCount === 1
      ) {
        options.holdActiveTaskOnce.onStarted()
        await options.holdActiveTaskOnce.release
      }
      if (
        options.failActiveAfterSuccessDeviceId === deviceId &&
        activeRequestCount > 1
      ) {
        return fulfillApiError(route, '当前任务后台刷新失败')
      }
      if (
        options.clearActiveAfterSuccessDeviceId === deviceId &&
        activeRequestCount > 1
      ) {
        return route.fulfill({ status: 204, body: '' })
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
        options.failDevicePage1Once &&
        pageNumber === 1 &&
        !devicePage1Succeeded &&
        !devicePage1InitialFailed
      ) {
        devicePage1InitialFailed = true
        return fulfillApiError(route, 'DATABASE_OPERATION_FAILED')
      }
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
      if (options.holdDevicePage2Once && pageNumber === 2 && !devicePage2Held) {
        devicePage2Held = true
        options.holdDevicePage2Once.onStarted()
        await options.holdDevicePage2Once.release
      }
      if (pageNumber === 1) devicePage1Succeeded = true
      const total = options.deviceTotal ?? 25
      const first = (pageNumber - 1) * pageSize + 1
      const last = Math.min(pageNumber * pageSize, total)
      return fulfillJson(route, {
        items:
          first > last
            ? []
            : Array.from({ length: last - first + 1 }, (_, index) =>
                makeDevice(first + index),
              ),
        total,
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
    }, testInfo) => {
      const consoleErrors = collectConsoleErrors(page)
      await page.setViewportSize({ width, height: 844 })
      await setThemeBeforeNavigation(page, theme)
      const state = await installMockApi(page, { deviceTotal: 8 })
      await page.goto('/#/devices')
      await applySafeAreaFixture(page)

      const firstCard = page.getByTestId('device-card').first()
      await expect(firstCard).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const themeButton = page.getByTestId('theme-toggle')
      const bellButton = page.getByRole('button', { name: '通知' })
      await expect(themeButton).toHaveAttribute(
        'aria-label',
        theme === 'light' ? '切换到深色主题' : '切换到浅色主题',
      )
      expect((await themeButton.boundingBox())?.height).toBeGreaterThanOrEqual(
        44,
      )
      expect((await bellButton.boundingBox())?.height).toBeGreaterThanOrEqual(
        44,
      )
      expect((await themeButton.boundingBox())!.x).toBeLessThan(
        (await bellButton.boundingBox())!.x,
      )
      await expect(firstCard.getByTestId('device-card-runtime')).toHaveText(
        '运行中',
      )
      await expect(firstCard).not.toContainText('同步订单')
      await expect(firstCard).not.toContainText('正在执行订单同步')
      await expect(firstCard.locator('.device-list-card__meta')).toContainText(
        /心跳 .*已启用/,
      )
      await expect(firstCard).not.toContainText('Worker')
      await expect(page.getByTestId('summary-all')).toHaveText('8')
      await expect(page.getByTestId('summary-online')).toHaveText('6')
      await expect(page.getByTestId('summary-running')).toHaveText('1')
      await expect(page.getByTestId('summary-offline')).toHaveText('1')
      await expect(page.locator('.mobile-summary-strip button')).toHaveCount(4)
      expect(
        await page
          .locator('.mobile-summary-strip button')
          .evaluateAll((buttons) =>
            buttons.every(
              (button) => button.getBoundingClientRect().height >= 44,
            ),
          ),
      ).toBe(true)
      await expect
        .poll(
          () =>
            new Set(
              state.activeTaskRequests.map((request) =>
                new URL(request).pathname.split('/').at(-1),
              ),
            ).size,
        )
        .toBe(8)
      const activeRequestCounts = new Map<string, number>()
      for (const request of state.activeTaskRequests) {
        const deviceId = new URL(request).pathname.split('/').at(-1) ?? ''
        activeRequestCounts.set(
          deviceId,
          (activeRequestCounts.get(deviceId) ?? 0) + 1,
        )
      }
      expect(activeRequestCounts.size).toBe(8)
      expect(
        [...activeRequestCounts.values()].every((count) => count >= 1),
      ).toBe(true)

      const mainButton = firstCard.getByRole('button', {
        name: '查看设备：设备 1',
      })
      expect((await mainButton.boundingBox())?.height).toBeGreaterThanOrEqual(
        44,
      )
      await expect(
        firstCard.getByRole('button', { name: '查看任务：同步订单' }),
      ).toHaveCount(0)
      expect((await firstCard.boundingBox())?.height).toBeLessThan(165)
      expect(
        await countCardsInsideListViewport(page, '[data-testid="device-card"]'),
      ).toBeGreaterThanOrEqual(3)
      expect(
        await isCardVisibleInsideListViewport(
          page,
          '[data-testid="device-card"]',
          3,
        ),
      ).toBe(true)

      const titleStyle = await firstCard
        .getByTestId('device-card-name')
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

      const cardAnatomy = await firstCard.evaluate((card) => {
        const box = (testId: string) =>
          card
            .querySelector<HTMLElement>(`[data-testid="${testId}"]`)!
            .getBoundingClientRect()
        const root = card.getBoundingClientRect()
        const leading = box('device-card-leading')
        const content = box('device-card-name')
        const chevron = box('device-card-chevron')
        const artwork = card
          .querySelector<HTMLElement>('.device-status-artwork')!
          .getBoundingClientRect()
        const chevronStyle = window.getComputedStyle(
          card.querySelector<HTMLElement>(
            '[data-testid="device-card-chevron"]',
          )!,
        )
        return {
          leadingLeft: leading.left,
          leadingRight: leading.right,
          leadingWidth: leading.width,
          artworkWidth: artwork.width,
          artworkHeight: artwork.height,
          contentLeft: content.left,
          contentRight: content.right,
          chevronWidth: chevron.width,
          chevronIconSize: Number.parseFloat(chevronStyle.fontSize),
          chevronRight: chevron.right,
          chevronCenterDelta: Math.abs(
            chevron.top + chevron.height / 2 - (root.top + root.height / 2),
          ),
        }
      })
      expect(cardAnatomy.leadingLeft).toBeLessThan(cardAnatomy.contentLeft)
      expect(cardAnatomy.leadingRight).toBeLessThanOrEqual(
        cardAnatomy.contentLeft,
      )
      expect(cardAnatomy.leadingWidth).toBe(102)
      expect(cardAnatomy.artworkWidth).toBe(80)
      expect(cardAnatomy.artworkHeight).toBe(80)
      expect(cardAnatomy.contentRight).toBeLessThanOrEqual(
        cardAnatomy.chevronRight,
      )
      expect(cardAnatomy.chevronWidth).toBe(16)
      expect(cardAnatomy.chevronIconSize).toBe(16)
      expect(cardAnatomy.chevronRight).toBeGreaterThan(cardAnatomy.contentRight)
      expect(cardAnatomy.chevronCenterDelta).toBeLessThanOrEqual(1)

      const overviewLayout = await page.evaluate(() => {
        const cards = Array.from(
          document.querySelectorAll<HTMLElement>('.mobile-summary-strip__item'),
        )
        const tokenColor = (token: string) => {
          const probe = document.createElement('span')
          probe.style.color = `var(${token})`
          document.body.append(probe)
          const color = window.getComputedStyle(probe).color
          probe.remove()
          return color
        }
        return {
          columnCount: window
            .getComputedStyle(
              document.querySelector<HTMLElement>(
                '.mobile-summary-strip__surface',
              )!,
            )
            .gridTemplateColumns.split(' ').length,
          tops: cards.map((card) => card.getBoundingClientRect().top),
          colors: cards.map(
            (card) =>
              window.getComputedStyle(
                card.querySelector<HTMLElement>(
                  '.mobile-summary-strip__value',
                )!,
              ).color,
          ),
          numberFontSizes: cards.map(
            (card) =>
              window.getComputedStyle(
                card.querySelector<HTMLElement>(
                  '.mobile-summary-strip__value',
                )!,
              ).fontSize,
          ),
          expectedNumberFontSize: window
            .getComputedStyle(document.documentElement)
            .getPropertyValue('--device-list-summary-value-size')
            .trim(),
          surfaceBackgrounds: [
            '.mobile-summary-strip__surface',
            '.device-list-card',
          ].map(
            (selector) =>
              window.getComputedStyle(
                document.querySelector<HTMLElement>(selector)!,
              ).backgroundColor,
          ),
          surfaceShadows: [
            '.mobile-summary-strip__surface',
            '.device-list-card',
          ].map(
            (selector) =>
              window.getComputedStyle(
                document.querySelector<HTMLElement>(selector)!,
              ).boxShadow,
          ),
          expectedSummaryBackground: tokenColor(
            '--device-list-summary-background',
          ),
          expectedCardBackground: tokenColor('--device-list-card-background'),
          expectedSummaryShadow: (() => {
            const probe = document.createElement('span')
            probe.style.boxShadow = 'var(--device-list-summary-shadow)'
            document.body.append(probe)
            const shadow = window.getComputedStyle(probe).boxShadow
            probe.remove()
            return shadow
          })(),
          expectedCardShadow: (() => {
            const probe = document.createElement('span')
            probe.style.boxShadow = 'var(--device-list-card-shadow)'
            document.body.append(probe)
            const shadow = window.getComputedStyle(probe).boxShadow
            probe.remove()
            return shadow
          })(),
          summaryToFirstCardGap:
            document
              .querySelector<HTMLElement>('.device-list-card')!
              .getBoundingClientRect().top -
            document
              .querySelector<HTMLElement>('.mobile-summary-strip__surface')!
              .getBoundingClientRect().bottom,
        }
      })
      expect(overviewLayout.columnCount).toBe(4)
      expect(new Set(overviewLayout.tops.map(Math.round)).size).toBe(1)
      expect(new Set(overviewLayout.colors).size).toBeLessThanOrEqual(2)
      expect(
        overviewLayout.numberFontSizes.every(
          (fontSize) => fontSize === overviewLayout.expectedNumberFontSize,
        ),
      ).toBe(true)
      expect(overviewLayout.surfaceBackgrounds).toEqual([
        overviewLayout.expectedSummaryBackground,
        overviewLayout.expectedCardBackground,
      ])
      expect(overviewLayout.surfaceShadows).toEqual([
        overviewLayout.expectedSummaryShadow,
        overviewLayout.expectedCardShadow,
      ])
      expect(overviewLayout.summaryToFirstCardGap).toBeCloseTo(14, 1)

      if (width === 390 && theme === 'light') {
        const meta = firstCard.locator('.device-list-card__meta')
        const metaBox = await meta.boundingBox()
        if (!metaBox) throw new Error('未找到设备非交互信息区域')
        await page.mouse.move(
          metaBox.x + metaBox.width / 2,
          metaBox.y + metaBox.height / 2,
        )
        await page.mouse.down()
        await expect
          .poll(() =>
            firstCard.evaluate(
              (element) => window.getComputedStyle(element).transform,
            ),
          )
          .not.toBe('none')
        await page.screenshot({
          path: testInfo.outputPath('device-card-pressed-390-light.png'),
        })
        await page.mouse.move(0, 0)
        await page.mouse.up()
        await expect
          .poll(() =>
            firstCard.evaluate(
              (element) => window.getComputedStyle(element).transform,
            ),
          )
          .toBe('none')
      }

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`device-list-390-${theme}.png`),
        })
      }

      const layout = await page.evaluate(() => {
        const style = (selector: string) => {
          const element = document.querySelector<HTMLElement>(selector)
          if (!element) throw new Error(`未找到布局节点：${selector}`)
          return window.getComputedStyle(element)
        }
        const controls = document
          .querySelector<HTMLElement>('[data-testid="device-list-controls"]')!
          .getBoundingClientRect()
        const listScroll = document
          .querySelector<HTMLElement>('[data-testid="device-list-scroll"]')!
          .getBoundingClientRect()
        const metricHeights = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.mobile-summary-strip__metric',
          ),
        ).map((element) => element.getBoundingClientRect().height)
        return {
          headerHeight: style('.mobile-global-header').height,
          searchHeight: style('.mobile-search-field').height,
          summaryHeight: style('.mobile-summary-strip').height,
          controlsLeft: style('[data-testid="device-list-controls"]')
            .paddingLeft,
          controlsRight: style('[data-testid="device-list-controls"]')
            .paddingRight,
          controlsBeforeList: controls.bottom <= listScroll.top + 0.5,
          metricHeights,
          listLeft: style('.device-list').paddingLeft,
          listRight: style('.device-list').paddingRight,
          listOverflowY: style('[data-testid="device-list-scroll"]').overflowY,
          listScrollbarWidth: style('[data-testid="device-list-scroll"]')
            .scrollbarWidth,
          shellMainOverflowY: style('.mobile-app-shell__main').overflowY,
          footerBottom: style('.mobile-app-shell__bottom').paddingBottom,
          bottomNavHeight: style('.van-tabbar').height,
          tabbarPosition: style('.van-tabbar').position,
        }
      })
      expect(layout).toMatchObject({
        headerHeight: '66px',
        searchHeight: '44px',
        summaryHeight: '90px',
        controlsLeft: safeAreaFixture.left,
        controlsRight: safeAreaFixture.right,
        controlsBeforeList: true,
        listLeft: safeAreaFixture.left,
        listRight: safeAreaFixture.right,
        listOverflowY: 'auto',
        listScrollbarWidth: 'none',
        shellMainOverflowY: 'hidden',
        footerBottom: safeAreaFixture.bottom,
        bottomNavHeight: '64px',
      })
      expect(layout.metricHeights.every((height) => height >= 44)).toBe(true)
      expect(layout.tabbarPosition).not.toBe('fixed')
      await expectNoHorizontalOverflow(page)

      await mainButton.click()
      await expect(page.getByTestId('device-detail')).toBeVisible()
      const hero = page.getByTestId('device-detail-hero')
      await expect(hero.getByTestId('device-hero-name')).toHaveText('设备 1')
      await expect(hero.getByTestId('device-hero-status')).toHaveText('运行中')
      await expect(hero.getByTestId('device-hero-heartbeat')).toContainText(
        '最后心跳：',
      )
      await expect(hero.getByTestId('device-hero-meta')).toContainText(
        /Worker \d/,
      )
      await expect(hero.getByTestId('device-hero-meta')).toContainText(
        '影刀 6.3.6',
      )
      await expect(hero).not.toContainText(/GY00099|5\.36\.1|Provider/)
      await expect(
        page.locator('.device-capability-panel__tab-label'),
      ).toHaveText(['影刀应用', 'Skills'])
      await expect(
        page.locator('.device-capability-panel__tab-count'),
      ).toHaveText(['1', '1'])
      for (const action of ['device-capability-refresh']) {
        const box = await page.getByTestId(action).boundingBox()
        expect(box?.width).toBeGreaterThanOrEqual(44)
        expect(box?.height).toBeGreaterThanOrEqual(44)
      }
      for (const actionName of ['配置：订单应用', '运行：订单应用']) {
        const box = await page
          .getByRole('button', { name: actionName })
          .boundingBox()
        expect(box?.width).toBeGreaterThanOrEqual(44)
        expect(box?.height).toBeGreaterThanOrEqual(44)
      }
      const refreshVisualSize = await page
        .getByTestId('device-capability-refresh')
        .evaluate((element) => {
          const style = window.getComputedStyle(element, '::before')
          return {
            width: Number.parseFloat(style.width),
            height: Number.parseFloat(style.height),
          }
        })
      expect(refreshVisualSize.height).toBe(34)
      expect(refreshVisualSize.width).toBeGreaterThanOrEqual(44)
      const capabilityActionVisualHeights = await page
        .locator(
          '.device-capability-panel__action > .van-button__content > span',
        )
        .evaluateAll((elements) =>
          elements.map((element) =>
            Number.parseFloat(window.getComputedStyle(element).height),
          ),
        )
      expect(capabilityActionVisualHeights).toEqual([34, 34])
      const capabilityActionBoxes = await Promise.all(
        ['配置：订单应用', '运行：订单应用'].map(async (name) =>
          page.getByRole('button', { name }).boundingBox(),
        ),
      )
      const [configureBox, runBox] = capabilityActionBoxes
      if (!configureBox || !runBox) {
        throw new Error('未找到能力操作触控区域')
      }
      expect(configureBox.x + configureBox.width <= runBox.x + 0.5).toBe(true)
      await expect(page.getByRole('button', { name: '返回' })).toBeVisible()
      await expect(page.getByRole('button', { name: '更多信息' })).toBeVisible()
      await expect(page.getByTestId('mobile-detail-header')).toHaveCSS(
        'height',
        '66px',
      )
      const detailSurfaces = await page.evaluate(() => {
        const selectors = [
          '[data-testid="device-detail-hero"]',
          '[data-testid="device-capability-panel"]',
          '[data-testid="device-current-task"] [data-testid="task-card"]',
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
          expectedDetailBackground: resolveColor(
            '--visual-v2-detail-surface-background',
          ),
          expectedBusinessBackground: resolveColor(
            '--visual-v2-business-card-background',
          ),
          expectedDetailShadow: resolveShadow(
            'var(--visual-v2-detail-surface-shadow)',
          ),
          expectedBusinessShadow: resolveShadow(
            'var(--visual-v2-business-card-shadow)',
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
        detailSurfaces.expectedDetailBackground,
        detailSurfaces.expectedDetailBackground,
        detailSurfaces.expectedBusinessBackground,
      ])
      expect(detailSurfaces.shadows).toEqual([
        detailSurfaces.expectedDetailShadow,
        detailSurfaces.expectedDetailShadow,
        detailSurfaces.expectedBusinessShadow,
      ])
      const currentTask = page.getByTestId('device-current-task')
      await expect(currentTask.getByTestId('task-card')).toBeVisible()
      await expect(currentTask.getByTestId('task-card-chevron')).toBeVisible()
      await expect(currentTask.locator('.van-progress')).toHaveCount(0)
      await expect(page.locator('.active-task-summary')).toHaveCount(0)
      await expect(page.getByTestId('device-detail')).not.toContainText(
        '企业账号',
      )
      await expect(
        page.getByTestId('device-capability-panel'),
      ).not.toContainText('未分类能力')
      if (width === 390 && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath('device-detail-390-light.png'),
        })
        const providerRequestsBeforeRefresh = state.providerRequests.length
        const capabilityRequestsBeforeRefresh = state.capabilityRequests.length
        await page.getByTestId('device-capability-refresh').click()
        await expect
          .poll(() => state.providerRequests.length)
          .toBeGreaterThan(providerRequestsBeforeRefresh)
        await expect
          .poll(() => state.capabilityRequests.length)
          .toBeGreaterThan(capabilityRequestsBeforeRefresh)

        const requestCountBeforeActions = state.methods.length
        for (const action of [
          page.getByRole('button', { name: '配置：订单应用' }),
          page.getByRole('button', { name: '运行：订单应用' }),
        ]) {
          await action.click()
          await expect(
            page.getByText('功能建设中', { exact: true }).last(),
          ).toBeVisible()
        }
        expect(state.methods).toHaveLength(requestCountBeforeActions)
        await expect(page.locator('body')).not.toContainText(
          /应用已启动|能力已刷新|参数已保存/,
        )
      }
      await page.getByRole('button', { name: '更多信息' }).click()
      const moreInformation = page.getByTestId('device-more-sheet')
      await expect(moreInformation).toBeVisible()
      await expect(
        page.getByTestId('provider-technical-details'),
      ).toContainText('企业账号是')
      await expect(
        page.getByTestId('capability-technical-details'),
      ).toContainText('未分类能力1 个')
      await expect(moreInformation).not.toContainText(/设备配置|更多设置/)
      await page.getByRole('button', { name: '关闭更多信息' }).click()
      await expect(moreInformation).toBeHidden()
      await expect(page.locator('.van-tabbar-item')).toHaveText([
        '设备',
        '任务',
        '计划',
        '店铺',
        '我的',
      ])
      await expect(
        page.locator('.van-tabbar-item--active').getByText('设备', {
          exact: true,
        }),
      ).toBeVisible()
      const detailSafeArea = await page
        .locator('.app-page')
        .evaluate((element) => {
          const style = window.getComputedStyle(element)
          return {
            left: style.paddingLeft,
            right: style.paddingRight,
            scrollbarWidth: style.scrollbarWidth,
          }
        })
      expect(detailSafeArea).toEqual({
        left: safeAreaFixture.left,
        right: safeAreaFixture.right,
        scrollbarWidth: 'none',
      })
      if (width === 390 && theme === 'light') {
        const detailScroll = page.getByRole('region', {
          name: '设备详情内容',
        })
        await detailScroll.evaluate((element) => {
          element.scrollTop = 0
        })
        await detailScroll.focus()
        await detailScroll.press('PageDown')
        await expect
          .poll(() => detailScroll.evaluate((element) => element.scrollTop))
          .toBeGreaterThan(0)
        await page.waitForTimeout(500)
        await detailScroll.evaluate((element) => {
          element.scrollTop = 0
          element.blur()
        })
        await expect
          .poll(() => detailScroll.evaluate((element) => element.scrollTop))
          .toBe(0)
      }
      await scrollDetailToBottom(page)
      await expectNoHorizontalOverflow(page)

      await page.getByRole('button', { name: '查看任务：同步订单' }).click()
      await expect(page).toHaveURL(
        /\/tasks\/task-active-1\?fromDeviceId=device-1$/,
      )
      await expect(page.getByTestId('task-detail')).toBeVisible()
      await expect(page.getByTestId('runtime-events')).toBeVisible()
      await expectNoHorizontalOverflow(page)
      expect(state.taskDetailRequests).toHaveLength(1)

      await page
        .getByTestId('mobile-detail-header')
        .getByRole('button', { name: '返回' })
        .click()
      await expect(page).toHaveURL(/\/devices\/device-1$/)
      await expect(page.getByTestId('device-detail')).toBeVisible()
      expect(state.methods.every((method) => method === 'GET')).toBe(true)
      expect(consoleErrors).toEqual([])
    })
  }
}

for (const height of [640, 740, 932] as const) {
  test(`设备列表在 390x${height} 真实高度下分配剩余空间并独立滚动`, async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.setViewportSize({ width: 390, height })
    await setThemeBeforeNavigation(page, 'light')
    await installMockApi(page, { deviceTotal: 20 })
    await page.goto('/#/devices')
    await expect(page.getByTestId('device-card')).toHaveCount(20)

    const before = await page.evaluate(() => {
      const box = (selector: string) =>
        document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
      const header = box('[data-testid="mobile-shell-header"]')
      const controls = box('[data-testid="device-list-controls"]')
      const list = box('[data-testid="device-list-scroll"]')
      const footer = box('[data-testid="mobile-shell-bottom"]')
      const scroll = document.querySelector<HTMLElement>(
        '[data-testid="device-list-scroll"]',
      )!
      return {
        viewport: { width: window.innerWidth, height: window.innerHeight },
        headerTop: header.top,
        controlsAfterHeader: controls.top >= header.bottom - 0.5,
        listAfterControls: list.top >= controls.bottom - 0.5,
        footerBottom: footer.bottom,
        listHeight: list.height,
        listScrollable: scroll.scrollHeight > scroll.clientHeight,
        documentScrollable:
          document.documentElement.scrollHeight >
          document.documentElement.clientHeight,
        horizontalOverflow:
          document.documentElement.scrollWidth > window.innerWidth,
      }
    })

    expect(before).toMatchObject({
      viewport: { width: 390, height },
      headerTop: 0,
      controlsAfterHeader: true,
      listAfterControls: true,
      footerBottom: height,
      listScrollable: true,
      documentScrollable: false,
      horizontalOverflow: false,
    })
    expect(before.listHeight).toBeGreaterThan(120)

    const list = page.getByTestId('device-list-scroll')
    await list.evaluate((element) => {
      element.scrollTop = 220
    })
    await expect
      .poll(() => list.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0)
    await expectNoHorizontalOverflow(page)
    expect(consoleErrors).toEqual([])
  })
}

test('20 条以上设备只滚动 Card List，固定区域保持原位', async ({
  page,
}, testInfo) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await setThemeBeforeNavigation(page, 'light')
  await installMockApi(page, { deviceTotal: 20 })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await expect(page.getByTestId('device-card')).toHaveCount(20)
  await expect(page.getByTestId('summary-running')).not.toHaveText('—')

  const readLayout = () =>
    page.evaluate(() => {
      const top = (selector: string) =>
        document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
          .top
      const scroll = document.querySelector<HTMLElement>(
        '[data-testid="device-list-scroll"]',
      )!
      return {
        headerTop: top('[data-testid="mobile-shell-header"]'),
        controlsTop: top('[data-testid="device-list-controls"]'),
        summaryTop: top('.mobile-summary-strip'),
        bottomTop: top('[data-testid="mobile-shell-bottom"]'),
        firstCardTop: top('[data-testid="device-card"]'),
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
  expect(before.listScrollable).toBe(true)
  expect(before.scrollbarWidth).toBe('none')
  expect(before.documentScrollable).toBe(false)
  const deviceScroll = page.getByTestId('device-list-scroll')
  await deviceScroll.focus()
  await page.keyboard.press('PageDown')
  await expect
    .poll(() => deviceScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  await page.waitForTimeout(500)
  await deviceScroll.evaluate((element) => {
    element.scrollTop = 0
    element.blur()
  })
  await expect
    .poll(() => deviceScroll.evaluate((element) => element.scrollTop))
    .toBe(0)
  await page.screenshot({
    path: testInfo.outputPath('layout-device-390-light-top.png'),
  })
  await deviceScroll.evaluate((element) => {
    element.scrollTop = 320
    element.dispatchEvent(new Event('scroll'))
  })
  await expect
    .poll(() => deviceScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  const after = await readLayout()

  expect(after.headerTop).toBeCloseTo(before.headerTop, 1)
  expect(after.controlsTop).toBeCloseTo(before.controlsTop, 1)
  expect(after.summaryTop).toBeCloseTo(before.summaryTop, 1)
  expect(after.bottomTop).toBeCloseTo(before.bottomTop, 1)
  expect(after.firstCardTop).toBeLessThan(before.firstCardTop)
  expect(after.shellScrollTop).toBe(0)
  expect(after.documentScrollTop).toBe(0)
  await page.screenshot({
    path: testInfo.outputPath('layout-device-390-light-mid.png'),
  })

  await scrollDeviceListToBottom(page)
  await expect(page.getByText('设备 20', { exact: true })).toBeVisible()
  await expect(page.getByTestId('mobile-shell-header')).toBeVisible()
  await expect(page.getByTestId('device-list-controls')).toBeVisible()
  await expect(page.getByTestId('mobile-shell-bottom')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})

test('设备列表按正式 20 条分页、下拉刷新并保持底部任务/设备导航', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page)
  const activeRequestCount = (deviceId: string) =>
    state.activeTaskRequests.filter((request) =>
      new URL(request).pathname.endsWith(`/${deviceId}`),
    ).length
  const firstPageDeviceIds = Array.from(
    { length: 20 },
    (_, index) => `device-${index + 1}`,
  )
  const secondPageDeviceIds = Array.from(
    { length: 5 },
    (_, index) => `device-${index + 21}`,
  )
  await page.goto('/#/devices')

  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await expect(page.getByTestId('summary-all')).toHaveText('25')
  await expect(page.getByTestId('summary-online')).toHaveText('—')
  await expect(page.getByTestId('summary-running')).toHaveText('—')
  await expect(page.getByTestId('summary-offline')).toHaveText('—')
  await expect(page.getByTestId('summary-metric-online')).toBeEnabled()
  await expect(page.getByTestId('summary-metric-running')).toBeEnabled()
  await expect(page.getByTestId('summary-metric-offline')).toBeEnabled()
  await expect(page.getByTestId('device-search')).toBeEnabled()
  await expect
    .poll(() => firstPageDeviceIds.map(activeRequestCount))
    .toEqual(firstPageDeviceIds.map(() => 1))
  const firstRequest = new URL(state.deviceListRequests[0] ?? '')
  expect(firstRequest.searchParams.get('page')).toBe('1')
  expect(firstRequest.searchParams.get('page_size')).toBe('20')
  expect([...firstRequest.searchParams.keys()].sort()).toEqual([
    'page',
    'page_size',
  ])

  const activeRequestIndexBeforePage2 = state.activeTaskRequests.length
  await scrollDeviceListToBottom(page)
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()
  await expect(page.getByTestId('summary-all')).toHaveText('25')
  await expect(page.getByTestId('summary-online')).toHaveText('23')
  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await expect(page.getByTestId('summary-offline')).toHaveText('1')
  await expect(page.getByTestId('summary-metric-online')).toBeEnabled()
  await expect(page.getByTestId('summary-metric-running')).toBeEnabled()
  await expect(page.getByTestId('summary-metric-offline')).toBeEnabled()
  await expect(page.getByTestId('device-search')).toBeEnabled()
  await expect
    .poll(() => secondPageDeviceIds.map(activeRequestCount))
    .toEqual(secondPageDeviceIds.map(() => 1))
  const newlyObservedDeviceIds = new Set(
    state.activeTaskRequests
      .slice(activeRequestIndexBeforePage2)
      .map((request) => new URL(request).pathname.split('/').at(-1) ?? '')
      .filter((deviceId) => !firstPageDeviceIds.includes(deviceId)),
  )
  expect([...newlyObservedDeviceIds].sort()).toEqual(
    [...secondPageDeviceIds].sort(),
  )
  expect(
    state.deviceListRequests.some((request) => {
      const params = new URL(request).searchParams
      return params.get('page') === '2' && params.get('page_size') === '20'
    }),
  ).toBe(true)

  await page.getByTestId('summary-metric-offline').click()
  await expect(page.getByTestId('summary-metric-offline')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await page.getByTestId('summary-metric-offline').click()
  await expect(page.getByTestId('device-card')).toHaveCount(25)

  await page.getByTestId('device-search').fill('设备 25')
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 25')
  await page.getByTestId('device-search').fill('')
  await expect(page.getByTestId('device-card')).toHaveCount(25)

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
  await expect(page.getByTestId('summary-all')).toHaveText('25')
  await expect(page.getByTestId('summary-online')).toHaveText('—')
  await page.waitForTimeout(100)
  const removedObserverRequestCounts =
    secondPageDeviceIds.map(activeRequestCount)
  await page.waitForTimeout(5_500)
  expect(secondPageDeviceIds.map(activeRequestCount)).toEqual(
    removedObserverRequestCounts,
  )

  await page.getByRole('tab', { name: /任务$/ }).click()
  await expect(page.getByTestId('task-card')).toBeVisible()
  await page.getByRole('tab', { name: /设备$/ }).click()
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  expect(consoleErrors).toEqual([])
})

test('设备页统一下拉刷新提供阈值、加载、成功反馈并防止重复请求', async ({
  page,
}) => {
  let notifyRefreshStarted: () => void = () => undefined
  const refreshStarted = new Promise<void>((resolve) => {
    notifyRefreshStarted = resolve
  })
  let releaseRefresh: () => void = () => undefined
  const refreshRelease = new Promise<void>((resolve) => {
    releaseRefresh = resolve
  })
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page, {
    deviceTotal: 1,
    holdDevicePage1AfterSuccessOnce: {
      onStarted: notifyRefreshStarted,
      release: refreshRelease,
    },
  })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(1)

  const requestsBeforeShortPull = state.deviceListRequests.length
  await pullBelowRefreshThreshold(page)
  await expect(page.getByTestId('mobile-pull-refresh-pulling')).toHaveCount(0)
  await page.waitForTimeout(280)
  expect(state.deviceListRequests).toHaveLength(requestsBeforeShortPull)

  await pullToRefresh(page)
  await refreshStarted
  await expect(
    page.getByTestId('mobile-pull-refresh').getByText('正在刷新', {
      exact: true,
    }),
  ).toBeVisible()
  const requestsWhileLoading = state.deviceListRequests.length

  await pullToRefresh(page)
  await page.waitForTimeout(250)
  expect(state.deviceListRequests).toHaveLength(requestsWhileLoading)

  releaseRefresh()
  await expect(page.getByTestId('mobile-pull-refresh-feedback')).toHaveText(
    '刷新完成',
  )
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  expect(consoleErrors).toEqual([])
})

test('设备页离开后忽略迟到的手动刷新反馈', async ({ page }) => {
  let notifyRefreshStarted: () => void = () => undefined
  const refreshStarted = new Promise<void>((resolve) => {
    notifyRefreshStarted = resolve
  })
  let releaseRefresh: () => void = () => undefined
  const refreshRelease = new Promise<void>((resolve) => {
    releaseRefresh = resolve
  })
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, {
    deviceTotal: 1,
    holdDevicePage1AfterSuccessOnce: {
      onStarted: notifyRefreshStarted,
      release: refreshRelease,
    },
  })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(1)

  await pullToRefresh(page)
  await refreshStarted
  await page.getByRole('tab', { name: /任务$/ }).click()
  await expect(page).toHaveURL(/#\/tasks$/)
  await expect(page.getByTestId('task-card')).toBeVisible()

  releaseRefresh()
  await page.waitForTimeout(650)
  await expect(page.getByTestId('mobile-pull-refresh-feedback')).toHaveCount(0)
  expect(consoleErrors).toEqual([])
})

test('未完成分页时点击快捷筛选会补齐全量结果并给出明确反馈', async ({
  page,
}) => {
  let notifyPage2Started: () => void = () => undefined
  const page2Started = new Promise<void>((resolve) => {
    notifyPage2Started = resolve
  })
  let releasePage2: () => void = () => undefined
  const page2Release = new Promise<void>((resolve) => {
    releasePage2 = resolve
  })
  const consoleErrors = collectConsoleErrors(page)

  await page.setViewportSize({ width: 390, height: 844 })
  const state = await installMockApi(page, {
    holdDevicePage2Once: {
      onStarted: notifyPage2Started,
      release: page2Release,
    },
  })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(20)

  await page.getByTestId('summary-metric-offline').tap()
  await page2Started
  await expect(page.getByTestId('summary-metric-offline')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-filter-preparing')).toContainText(
    '正在筛选',
  )

  releasePage2()
  await expect(page.getByTestId('summary-online')).toHaveText('23')
  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await expect(page.getByTestId('summary-offline')).toHaveText('1')
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 2')
  await expect(page.getByTestId('device-card').first()).toContainText('离线')

  expect(
    state.deviceListRequests.some((request) => {
      const params = new URL(request).searchParams
      return params.get('page') === '2' && params.get('page_size') === '20'
    }),
  ).toBe(true)
  expect(
    state.deviceListRequests.every((request) =>
      [...new URL(request).searchParams.keys()].every((key) =>
        ['page', 'page_size'].includes(key),
      ),
    ),
  ).toBe(true)

  await page.getByTestId('summary-metric-offline').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(25)
  await page.getByTestId('summary-metric-online').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(23)
  await page.getByTestId('summary-metric-running').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 1')
  await page.getByTestId('summary-metric-running').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(25)

  await page.getByTestId('summary-metric-online').tap()
  await page.getByTestId('device-search').fill('设备 25')
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 25')
  await page.getByTestId('device-search').fill('')
  await expect(page.getByTestId('device-card')).toHaveCount(23)
  await page.getByTestId('summary-metric-online').tap()

  await page.getByTestId('summary-metric-offline').tap()
  const requestCountBeforeRefresh = state.deviceListRequests.length
  await pullToRefresh(page)
  await expect
    .poll(() => state.deviceListRequests.length)
    .toBeGreaterThan(requestCountBeforeRefresh)
  await expect(page.getByTestId('summary-metric-offline')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 2')
  expect(
    state.deviceListRequests
      .slice(requestCountBeforeRefresh)
      .some((request) => new URL(request).searchParams.get('page') === '2'),
  ).toBe(true)

  await expectNoHorizontalOverflow(page)
  expect(consoleErrors).toEqual([])
})

test('计数为零的快捷筛选仍可选中并展示正式空态', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await installMockApi(page, { deviceTotal: 1 })
  await page.goto('/#/devices')

  await expect(page.getByTestId('summary-offline')).toHaveText('0')
  await expect(page.getByTestId('summary-metric-offline')).toBeEnabled()
  await page.getByTestId('summary-metric-offline').tap()
  await expect(page.getByTestId('summary-metric-offline')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-empty')).toContainText('没有设备')

  await page.getByTestId('summary-metric-offline').tap()
  await expect(page.getByTestId('summary-metric-all')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-card')).toHaveCount(1)
})

test('运行中筛选随后台 Active Task 事实更新且保留选中态', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  const state = await installMockApi(page, {
    deviceTotal: 1,
    clearActiveAfterSuccessDeviceId: 'device-1',
  })
  await page.goto('/#/devices')

  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await page.getByTestId('summary-metric-running').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect
    .poll(
      () =>
        state.activeTaskRequests.filter((request) =>
          new URL(request).pathname.endsWith('/device-1'),
        ).length,
      { timeout: 8_000 },
    )
    .toBeGreaterThan(1)

  await expect(page.getByTestId('summary-running')).toHaveText('0')
  await expect(page.getByTestId('summary-metric-running')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-empty')).toBeVisible()
  expect(consoleErrors).toEqual([])
})

test('运行中事实首次失败时筛选可显式重试并得到完整结果', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, {
    deviceTotal: 1,
    failActiveOnceDeviceId: 'device-1',
  })
  await page.goto('/#/devices')

  await expect(page.getByTestId('summary-running')).toHaveText('—')
  await page.getByTestId('summary-metric-running').tap()
  await expect(page.getByTestId('device-filter-error')).toContainText(
    '筛选失败',
  )

  await page
    .getByTestId('device-filter-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByTestId('device-filter-error')).toHaveCount(0)
  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('运行中')
})

test('设备后台刷新失败保留旧卡片且不展示实现原因', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, { failDevicePage1AfterSuccessOnce: true })
  await page.goto('/#/devices')
  await applySafeAreaFixture(page)
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await scrollDeviceListToBottom(page)
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()

  await pullToRefresh(page)
  await expect(page.getByText('刷新失败', { exact: true })).toBeVisible()
  await expect(page.getByTestId('mobile-pull-refresh-feedback')).toHaveText(
    '刷新失败',
  )
  await expect(page.getByTestId('device-background-error')).toHaveCount(0)
  await expect(page.getByText('设备后台刷新失败')).toHaveCount(0)
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()
  await expect(page.getByTestId('summary-all')).toHaveText('25')
  await expect(page.getByTestId('summary-online')).toHaveText('23')
  await expectNoHorizontalOverflow(page)
})

test('设备首次请求失败进入简洁错误并可重试成功', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, { failDevicePage1Once: true })
  await page.goto('/#/devices')

  const errorState = page.getByTestId('device-error')
  await expect(errorState).toBeVisible()
  await expect(errorState).toContainText('加载失败')
  await expect(errorState).not.toContainText('DATABASE_OPERATION_FAILED')
  await expect(page.getByTestId('device-loading')).toHaveCount(0)
  await expect(page.getByTestId('mobile-shell-header')).toBeVisible()
  await expect(page.locator('.mobile-summary-strip')).toBeVisible()
  await expect(page.getByTestId('device-list-controls')).toBeVisible()
  await expect(page.getByTestId('mobile-shell-bottom')).toBeVisible()
  expect(
    await errorState.evaluate(
      (element) =>
        element.closest('[data-testid="device-list-scroll"]') !== null,
    ),
  ).toBe(true)

  await errorState.getByRole('button', { name: '重试' }).click()
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await expect(page.getByTestId('device-error')).toHaveCount(0)
})

test('Active Task 部分未知时不显示伪零并在补齐后转为精确统计', async ({
  page,
}) => {
  let notifyActiveStarted: () => void = () => undefined
  const activeStarted = new Promise<void>((resolve) => {
    notifyActiveStarted = resolve
  })
  let releaseActive: () => void = () => undefined
  const activeRelease = new Promise<void>((resolve) => {
    releaseActive = resolve
  })

  await installMockApi(page, {
    deviceTotal: 20,
    holdActiveTaskOnce: {
      deviceId: 'device-1',
      onStarted: notifyActiveStarted,
      release: activeRelease,
    },
  })
  await page.goto('/#/devices')
  await activeStarted

  await expect(page.getByTestId('summary-running')).toHaveText('—')

  releaseActive()
  await expect(page.getByTestId('summary-running')).toHaveText('1')
})

test('Active Task 缓存背景失败保留运行中数量并提示刷新失败', async ({
  page,
}) => {
  const state = await installMockApi(page, {
    deviceTotal: 20,
    failActiveAfterSuccessDeviceId: 'device-1',
  })
  await page.goto('/#/devices')

  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await expect
    .poll(
      () =>
        state.activeTaskRequests.filter((request) =>
          new URL(request).pathname.endsWith('/device-1'),
        ).length,
      { timeout: 8_000 },
    )
    .toBeGreaterThan(1)
  await expect(page.getByTestId('summary-running')).toHaveText('1')
  await expect(page.getByText('当前任务后台刷新失败')).toHaveCount(0)
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
  await expect(page.getByTestId('device-card').first()).toBeVisible()
  await scrollDeviceListToBottom(page)
  await page.clock.runFor(100)
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

test('筛选补齐下一页失败时不展示局部结果并可显式重试', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installMockApi(page, { failDevicePage2Once: true })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(20)

  await page.getByTestId('summary-metric-offline').tap()
  await expect(page.getByTestId('summary-metric-offline')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByTestId('device-filter-error')).toContainText(
    '筛选失败',
  )
  await expect(page.getByTestId('device-card')).toHaveCount(0)

  await page
    .getByTestId('device-filter-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByTestId('device-filter-error')).toHaveCount(0)
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 2')
})

test('设备下一页失败只在尾部提示并可显式重试', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installMockApi(page, { failDevicePage2Once: true })
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card').first()).toBeVisible()

  await scrollDeviceListToBottom(page)
  await expect(page.getByTestId('device-list-next-page-error')).toBeVisible()
  await expect(page.getByTestId('device-background-error')).toHaveCount(0)
  await page
    .getByTestId('device-list-next-page-error')
    .getByRole('button', { name: '重试' })
    .click()
  await expect(page.getByText('设备 25', { exact: true })).toBeVisible()
})

test('设备详情成功时三类辅助失败各自展示且不覆盖主数据', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  const state = await installMockApi(page, { failAuxiliary: true })
  await page.goto('/#/devices/device-1')

  await expect(page.getByTestId('device-detail')).toBeVisible()
  await expect(page.getByText('设备 1', { exact: true })).toBeVisible()
  await expect(page.getByText('加载失败', { exact: true })).toHaveCount(2)
  await page.getByRole('tab', { name: /Skills/ }).click()
  await expect(page.getByText('加载失败', { exact: true })).toHaveCount(2)
  await expect(page.locator('body')).not.toContainText(
    /影刀快照加载失败|技能能力加载失败/,
  )
  expect(state.activeTaskRequests.length).toBeGreaterThan(0)
  expect(state.providerRequests).toHaveLength(1)
  expect(state.capabilityRequests).toHaveLength(1)
  await expectNoHorizontalOverflow(page)
})

test('Runtime缺失显示未连接且不会混入正式离线筛选', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installMockApi(page, { deviceTotal: 3 })

  await page.goto('/#/devices')
  await expect(page.getByTestId('summary-offline')).toHaveText('1')
  const unreportedCard = page
    .getByTestId('device-card')
    .filter({ hasText: '设备 3' })
  await expect(unreportedCard.getByTestId('device-card-runtime')).toHaveText(
    '未连接',
  )
  await expect(
    unreportedCard.getByTestId('device-status-artwork'),
  ).toHaveAttribute('data-device-artwork-state', 'offline')
  await page.getByTestId('summary-metric-offline').tap()
  await expect(page.getByTestId('device-card')).toHaveCount(1)
  await expect(page.getByTestId('device-card').first()).toContainText('设备 2')
  await expect(page.getByTestId('device-list')).not.toContainText('设备 3')

  await page.goto('/#/devices/device-3')
  await expect(page.getByTestId('device-detail')).toContainText('未上报')
  await expect(page.getByTestId('device-detail')).toContainText('未连接')
  await expect(page.getByTestId('device-detail')).not.toContainText('离线')

  await page.goto('/#/devices/device-2')
  await expect(page.getByTestId('device-detail')).toContainText('离线')
  await expect(page.getByTestId('device-detail')).toContainText('待执行')
  await expect(page.getByTestId('device-detail')).not.toContainText('未上报')
})
