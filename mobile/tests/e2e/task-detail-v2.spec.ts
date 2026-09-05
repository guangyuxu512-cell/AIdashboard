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

interface MockOptions {
  emptyEvents?: boolean
  failEventsOnce?: boolean
  failTaskOnce?: boolean
  deviceDelayMs?: number
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function setThemeBeforeNavigation(
  page: Page,
  theme: (typeof themes)[number],
): Promise<void> {
  await page.addInitScript((mode) => {
    window.localStorage.setItem('control-center.mobile.theme-mode', mode)
  }, theme)
}

async function applySafeAreaFixture(page: Page): Promise<void> {
  await page.evaluate(() => {
    const root = document.documentElement
    root.style.setProperty('--safe-area-top', '19px')
    root.style.setProperty('--safe-area-right', '11px')
    root.style.setProperty('--safe-area-bottom', '23px')
    root.style.setProperty('--safe-area-left', '10px')
  })
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function fulfillError(route: Route): Promise<void> {
  await route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({
      code: 'DATABASE_OPERATION_FAILED',
      message: '仅供测试的技术错误',
      request_id: 'request-task-detail-v2',
      details: null,
    }),
  })
}

function makeTaskDetail() {
  const now = Date.now()
  return {
    task_id: 'task-detail-v2',
    target_device_id: 'device-detail-v2',
    shop_ids: [],
    asset_ids: [],
    skill_id: 'internal-order-sync',
    execution_display_name:
      '跨境电商多平台每日订单同步与售后状态核对任务（华东运营组）',
    status: 'running',
    input: {},
    result: null,
    error_code: null,
    error_message: null,
    lease_until: null,
    started_at: new Date(now - 3 * 60_000).toISOString(),
    finished_at: null,
    runtime_events_purged_at: null,
    created_at: new Date(now - 4 * 60_000).toISOString(),
    updated_at: new Date(now).toISOString(),
  }
}

function makeDevice() {
  return {
    device_id: 'device-detail-v2',
    display_name: '华东售后协同中心自动化执行设备一号（夜间值守）',
    enabled: true,
    location: null,
    note: null,
    deleted_at: null,
    worker_runtime: null,
    created_at: '2026-08-01T00:00:00.000Z',
    updated_at: '2026-08-26T01:05:00.000Z',
  }
}

function makeEvents() {
  return Array.from({ length: 14 }, (_, index) => {
    const seq = index + 1
    const eventType =
      seq === 14
        ? 'progress'
        : seq % 5 === 0
          ? 'log'
          : seq % 3 === 0
            ? 'progress'
            : 'status'
    return {
      event_id: `event-${seq}`,
      task_id: 'task-detail-v2',
      seq,
      event_type: eventType,
      level: 'info',
      message: `第 ${seq} 条真实事件消息`,
      event_at: `2026-08-26T01:${String(seq).padStart(2, '0')}:00.000Z`,
      metadata: eventType === 'progress' ? { current: seq, total: 20 } : {},
      created_at: `2026-08-26T01:${String(seq).padStart(2, '0')}:00.000Z`,
    }
  })
}

async function installTaskDetailApi(
  page: Page,
  options: MockOptions = {},
): Promise<void> {
  const auth = createMobileAuthApiFixture()
  let eventsFailureUsed = false
  let taskFailureUsed = false

  await page.route('**/api/v1/**', async (route) => {
    if (await auth.handle(route)) return
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/^.*\/api\/v1\//, '')

    if (path === 'tasks/task-detail-v2/events') {
      if (options.failEventsOnce && !eventsFailureUsed) {
        eventsFailureUsed = true
        return fulfillError(route)
      }
      const events = options.emptyEvents ? [] : makeEvents()
      const afterSequence = Number(url.searchParams.get('after_seq') ?? 0)
      const items = afterSequence
        ? events.filter((event) => event.seq > afterSequence)
        : events
      return fulfillJson(route, {
        task_id: 'task-detail-v2',
        after_seq: url.searchParams.has('after_seq') ? afterSequence : null,
        before_seq: null,
        next_after_seq: items.at(-1)?.seq ?? afterSequence,
        next_before_seq: null,
        has_more_before: false,
        items,
      })
    }

    if (path === 'tasks/task-detail-v2') {
      if (options.failTaskOnce && !taskFailureUsed) {
        taskFailureUsed = true
        return fulfillError(route)
      }
      return fulfillJson(route, makeTaskDetail())
    }

    if (path === 'devices/device-detail-v2') {
      if (options.deviceDelayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.deviceDelayMs),
        )
      }
      return fulfillJson(route, makeDevice())
    }

    return fulfillError(route)
  })
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

for (const viewport of viewports) {
  for (const theme of themes) {
    test(`Task Detail V2 ${viewport.width}×${viewport.height} ${theme} 只滚动日志且保持真实字段`, async ({
      page,
    }, testInfo) => {
      const consoleErrors = collectConsoleErrors(page)
      await page.setViewportSize(viewport)
      await setThemeBeforeNavigation(page, theme)
      await installTaskDetailApi(page)
      await page.goto('/#/tasks/task-detail-v2')
      await applySafeAreaFixture(page)

      await expect(page.getByTestId('task-detail')).toBeVisible()
      await expect(page.getByTestId('mobile-detail-header-title')).toHaveText(
        '任务详情',
      )
      await expect(page.getByTestId('task-detail-status')).toContainText(
        '执行中',
      )
      await expect(page.getByTestId('task-detail-info-started')).toContainText(
        '开始时间',
      )
      await expect(page.getByTestId('task-detail-info-device')).toContainText(
        '华东售后协同中心',
      )
      await expect(
        page.getByTestId('runtime-events').locator('li'),
      ).toHaveCount(14)
      await expect(
        page.getByTestId('runtime-events').locator('li').first(),
      ).toContainText('第 1 条真实事件消息')
      await expect(
        page.getByTestId('runtime-events').locator('li').last(),
      ).toContainText('第 14 条真实事件消息')
      await expect(
        page.locator('.van-tabbar-item--active').getByText('任务', {
          exact: true,
        }),
      ).toBeVisible()
      await expect(page.locator('.mobile-detail-header__action')).toHaveCount(0)
      await expect(
        page.locator('[data-testid="task-card-chevron"]'),
      ).toHaveCount(0)
      await expect(page.locator('body')).not.toContainText('触发方式')
      await expect(page.locator('body')).not.toContainText('执行账号')
      await expect(page.locator('body')).not.toContainText('Provider')
      await expect(page.locator('body')).not.toContainText(
        'internal-order-sync',
      )

      const before = await page.evaluate(() => {
        const box = (selector: string) =>
          document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
        const pageRoot = document.querySelector<HTMLElement>(
          '[data-testid="task-detail-page"]',
        )!
        const log = document.querySelector<HTMLElement>(
          '[data-testid="runtime-log"]',
        )!
        const scroll = document.querySelector<HTMLElement>(
          '[data-testid="runtime-log-scroll"]',
        )!
        const heading = log.querySelector<HTMLElement>('.runtime-log__heading')!
        const title = document.querySelector<HTMLElement>(
          '[data-testid="task-detail-title"]',
        )!
        const deviceValue = document.querySelector<HTMLElement>(
          '[data-testid="task-detail-info-device"] dd',
        )!
        const titleStyle = getComputedStyle(title)
        const deviceStyle = getComputedStyle(deviceValue)
        return {
          card: box('[data-testid="task-detail"]'),
          log: box('[data-testid="runtime-log"]'),
          heading: heading.getBoundingClientRect(),
          bottom: box('[data-testid="mobile-shell-bottom"]'),
          pageOverflowY: getComputedStyle(pageRoot).overflowY,
          logOverflowY: getComputedStyle(scroll).overflowY,
          logScrollable: scroll.scrollHeight > scroll.clientHeight,
          headingOutsideScroll: !scroll.contains(heading),
          documentScrollable:
            document.documentElement.scrollHeight > window.innerHeight,
          titleOverflow: [
            titleStyle.overflow,
            titleStyle.textOverflow,
            titleStyle.whiteSpace,
          ],
          deviceOverflow: [
            deviceStyle.overflow,
            deviceStyle.textOverflow,
            deviceStyle.whiteSpace,
          ],
        }
      })

      expect(before.card.bottom).toBeLessThan(before.log.top)
      expect(before.heading.top).toBeGreaterThanOrEqual(before.log.top)
      expect(before.log.bottom).toBeLessThanOrEqual(before.bottom.top)
      expect(before.pageOverflowY).toBe('hidden')
      expect(before.logOverflowY).toBe('auto')
      expect(before.logScrollable).toBe(true)
      expect(before.headingOutsideScroll).toBe(true)
      expect(before.documentScrollable).toBe(false)
      expect(before.titleOverflow).toEqual(['hidden', 'ellipsis', 'nowrap'])
      expect(before.deviceOverflow).toEqual(['hidden', 'ellipsis', 'nowrap'])

      if (
        viewport.width === 390 ||
        (viewport.width === 360 && theme === 'light')
      ) {
        await page.screenshot({
          path: testInfo.outputPath(
            `task-detail-v2-${viewport.width}-${theme}.png`,
          ),
        })
      }

      await page.getByTestId('runtime-log-scroll').evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
      const after = await page.evaluate(() => {
        const box = (selector: string) =>
          document.querySelector<HTMLElement>(selector)!.getBoundingClientRect()
        return {
          cardTop: box('[data-testid="task-detail"]').top,
          headingTop: box('.runtime-log__heading').top,
          bottomTop: box('[data-testid="mobile-shell-bottom"]').top,
          logScrollTop: document.querySelector<HTMLElement>(
            '[data-testid="runtime-log-scroll"]',
          )!.scrollTop,
        }
      })
      expect(after.cardTop).toBeCloseTo(before.card.top, 1)
      expect(after.headingTop).toBeCloseTo(before.heading.top, 1)
      expect(after.bottomTop).toBeCloseTo(before.bottom.top, 1)
      expect(after.logScrollTop).toBeGreaterThan(0)

      await expectNoHorizontalOverflow(page)
      expect(consoleErrors).toEqual([])
    })
  }
}

test('Task基础信息成功时，Device与Events保持独立局部状态', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installTaskDetailApi(page, {
    deviceDelayMs: 250,
    failEventsOnce: true,
  })
  await page.goto('/#/tasks/task-detail-v2')

  await expect(page.getByTestId('task-detail-title')).toBeVisible()
  await expect(page.getByTestId('task-detail-info-device')).toContainText(
    '加载中',
  )
  await expect(page.getByTestId('runtime-log-error')).toContainText('加载失败')
  await expect(page.getByTestId('task-detail')).toBeVisible()

  await page
    .getByTestId('runtime-log-error')
    .getByRole('button', {
      name: '重试',
    })
    .click()
  await expect(page.getByTestId('runtime-events').locator('li')).toHaveCount(14)
  await expect(page.getByTestId('task-detail-info-device')).toContainText(
    '华东售后协同中心',
  )
  await expect(page.locator('body')).not.toContainText(
    'DATABASE_OPERATION_FAILED',
  )
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource'),
    ),
  ).toEqual([])
})

test('空日志与Task初始失败都进入确定状态并支持重试', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installTaskDetailApi(page, { emptyEvents: true, failTaskOnce: true })
  await page.goto('/#/tasks/task-detail-v2')

  await expect(page.getByTestId('task-detail-error')).toContainText('加载失败')
  await page
    .getByTestId('task-detail-error')
    .getByRole('button', {
      name: '重试',
    })
    .click()
  await expect(page.getByTestId('task-detail')).toBeVisible()
  await expect(page.getByTestId('runtime-log-empty')).toHaveText('暂无运行日志')
  await expect(page.getByTestId('detail-loading')).toHaveCount(0)
})
