import { expect, test, type Page } from '@playwright/test'

const safeAreaFixture = {
  top: '19px',
  right: '22px',
  bottom: '23px',
  left: '21px',
} as const

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

async function installShellReadOnlyApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') {
      await route.fulfill({ status: 405 })
      return
    }

    const url = new URL(request.url())
    if (url.pathname === '/api/v1/devices') {
      const items = Array.from({ length: 20 }, (_, index) => ({
        device_id: `shell-device-${index + 1}`,
        display_name: `壳层验证设备 ${index + 1}`,
        enabled: true,
        location: null,
        note: null,
        deleted_at: null,
        worker_runtime: null,
        created_at: '2026-08-26T00:00:00.000Z',
        updated_at: '2026-08-26T00:00:00.000Z',
      }))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items, total: 20, page: 1, page_size: 20 }),
      })
      return
    }
    if (url.pathname.startsWith('/api/v1/tasks/active/')) {
      await route.fulfill({ status: 204 })
      return
    }
    if (url.pathname === '/api/v1/tasks') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
      })
      return
    }

    await route.fulfill({ status: 404 })
  })
}

test('AppShell V2统一品牌栏、五入口导航与建设中页', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await installShellReadOnlyApi(page)
  await page.goto('/#/devices')
  await applySafeAreaFixture(page)

  await expect(page.getByText('共 20 台设备', { exact: true })).toBeVisible()

  await expect(page.getByTestId('mobile-global-header')).toContainText(
    '思余AI中控台',
  )
  await expect(page.getByRole('button', { name: '通知' })).toBeVisible()
  await expect(page.locator('.van-badge--dot')).toHaveCount(0)
  expect(
    (await page.getByRole('button', { name: '通知' }).boundingBox())?.height,
  ).toBeGreaterThanOrEqual(44)

  const tabbarItems = page.locator('.van-tabbar-item')
  await expect(tabbarItems).toHaveText(['设备', '任务', '计划', '店铺', '我的'])
  await expect(
    page.locator('.van-tabbar-item--active').getByText('设备', {
      exact: true,
    }),
  ).toBeVisible()

  const chromeVisual = await page.evaluate(() => {
    const style = (selector: string) => {
      const element = document.querySelector<HTMLElement>(selector)
      if (!element) throw new Error(`未找到壳层视觉节点：${selector}`)
      return window.getComputedStyle(element)
    }
    const tokenColor = (token: string, property: 'color' | 'background') => {
      const probe = document.createElement('span')
      probe.style[property] = `var(${token})`
      document.body.append(probe)
      const value =
        window.getComputedStyle(probe)[
          property === 'color' ? 'color' : 'backgroundColor'
        ]
      probe.remove()
      return value
    }
    const root = window.getComputedStyle(document.documentElement)
    return {
      headerBackground: style('.mobile-global-header').backgroundColor,
      bottomBackground: style('.mobile-bottom-navigation').backgroundColor,
      expectedRaised: tokenColor('--bg-surface-raised', 'background'),
      activeColor: style('.van-tabbar-item--active').color,
      inactiveColor: style('.van-tabbar-item:not(.van-tabbar-item--active)')
        .color,
      expectedActive: tokenColor('--text-selected', 'color'),
      expectedInactive: tokenColor('--text-tertiary', 'color'),
      brandFontSize: style('.mobile-global-header__brand').fontSize,
      expectedBrandFontSize: root.getPropertyValue('--font-size-label').trim(),
    }
  })
  expect(chromeVisual).toEqual({
    headerBackground: chromeVisual.expectedRaised,
    bottomBackground: chromeVisual.expectedRaised,
    expectedRaised: chromeVisual.expectedRaised,
    activeColor: chromeVisual.expectedActive,
    inactiveColor: chromeVisual.expectedInactive,
    expectedActive: chromeVisual.expectedActive,
    expectedInactive: chromeVisual.expectedInactive,
    brandFontSize: chromeVisual.expectedBrandFontSize,
    expectedBrandFontSize: chromeVisual.expectedBrandFontSize,
  })

  const shellGeometry = await page.evaluate(() => {
    const header = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-header"]',
    )
    const main = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-main"]',
    )
    const bottom = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-bottom"]',
    )
    if (!header || !main || !bottom) throw new Error('AppShell区域不完整')
    const headerBox = header.getBoundingClientRect()
    const mainBox = main.getBoundingClientRect()
    const bottomBox = bottom.getBoundingClientRect()
    return {
      headerTopPadding: getComputedStyle(header).paddingTop,
      bottomPadding: getComputedStyle(bottom).paddingBottom,
      headerBeforeMain: headerBox.bottom <= mainBox.top,
      mainBeforeBottom: mainBox.bottom <= bottomBox.top,
      bottomWithinViewport: bottomBox.bottom <= window.innerHeight,
      noHorizontalOverflow:
        document.documentElement.scrollWidth <= window.innerWidth,
    }
  })
  expect(shellGeometry).toEqual({
    headerTopPadding: safeAreaFixture.top,
    bottomPadding: safeAreaFixture.bottom,
    headerBeforeMain: true,
    mainBeforeBottom: true,
    bottomWithinViewport: true,
    noHorizontalOverflow: true,
  })

  const firstTabBox = await tabbarItems.first().boundingBox()
  expect(firstTabBox?.height).toBeGreaterThanOrEqual(44)

  await page.getByRole('tab', { name: /任务/ }).click()
  await expect(page).toHaveURL(/#\/tasks$/)
  await expect(
    page.locator('.van-tabbar-item--active').getByText('任务', {
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('tab', { name: /设备/ }).click()
  await expect(page).toHaveURL(/#\/devices$/)

  await page.getByRole('tab', { name: /计划/ }).click()
  await expect(page).toHaveURL(/#\/schedules$/)
  await expect(
    page.getByRole('heading', { name: '定时计划', level: 1 }),
  ).toBeVisible()
  await expect(page.getByText('功能建设中', { exact: true })).toBeVisible()

  await page.getByRole('tab', { name: /店铺/ }).click()
  await expect(page).toHaveURL(/#\/shops$/)
  await expect(
    page.getByRole('heading', { name: '店铺', level: 1 }),
  ).toBeVisible()

  await page.getByRole('tab', { name: /我的/ }).click()
  await expect(page).toHaveURL(/#\/me$/)
  await expect(
    page.getByRole('heading', { name: '我的', level: 1 }),
  ).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/管理员|假账号|假昵称/)

  await page.getByRole('button', { name: '通知' }).click()
  await expect(page.getByText('通知功能建设中', { exact: true })).toBeVisible()

  await page.evaluate(() => {
    window.localStorage.setItem('control-center.mobile.theme-mode', 'dark')
  })
  await page.reload()
  await page.goto('/#/__foundation')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('button', { name: '返回' })).toBeVisible()

  const detailHeaderVisual = await page.evaluate(() => {
    const navBar = document.querySelector<HTMLElement>(
      '.mobile-detail-header .van-nav-bar',
    )
    if (!navBar) throw new Error('未找到详情返回栏')
    const probe = document.createElement('span')
    probe.style.background = 'var(--bg-surface-raised)'
    document.body.append(probe)
    const expectedRaised = window.getComputedStyle(probe).backgroundColor
    probe.remove()
    return {
      background: window.getComputedStyle(navBar).backgroundColor,
      expectedRaised,
    }
  })
  expect(detailHeaderVisual.background).toBe(detailHeaderVisual.expectedRaised)

  const backButton = page.getByRole('button', { name: '返回' })
  expect((await backButton.boundingBox())?.height).toBeGreaterThanOrEqual(44)
  await page.keyboard.press('Tab')
  await expect(backButton).toBeFocused()
  const backFocus = await backButton.evaluate((element) => {
    const style = window.getComputedStyle(element)
    return { style: style.outlineStyle, width: style.outlineWidth }
  })
  expect(backFocus).toEqual({ style: 'solid', width: '2px' })
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#\/$/)

  expect(consoleErrors).toEqual([])
})
