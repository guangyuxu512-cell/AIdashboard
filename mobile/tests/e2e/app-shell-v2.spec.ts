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

  await expect(page.getByTestId('summary-all')).toHaveText('20')

  await expect(page.getByTestId('mobile-global-header')).toContainText('设备')
  const headerButtons = page
    .getByTestId('mobile-global-header')
    .getByRole('button')
  await expect(headerButtons).toHaveCount(3)
  await expect(headerButtons.nth(0)).toHaveAttribute(
    'aria-label',
    '打开主题设置',
  )
  await expect(headerButtons.nth(1)).toHaveAttribute(
    'aria-label',
    /切换到(浅色|深色)主题/,
  )
  await expect(headerButtons.nth(2)).toHaveAttribute('aria-label', '通知')
  await expect(page.getByRole('button', { name: '通知' })).toBeVisible()
  await expect(page.locator('.van-badge--dot')).toHaveCount(0)
  expect(
    (await page.getByRole('button', { name: '通知' }).boundingBox())?.height,
  ).toBeGreaterThanOrEqual(44)
  expect(
    (await headerButtons.nth(0).boundingBox())?.height,
  ).toBeGreaterThanOrEqual(44)

  const initialTheme = await page.locator('html').getAttribute('data-theme')
  await headerButtons.nth(0).click()
  await expect(page.getByRole('dialog')).toContainText(
    '浅色主题深色主题跟随系统',
  )
  await page
    .getByRole('button', {
      name: initialTheme === 'dark' ? '深色主题' : '浅色主题',
    })
    .click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await headerButtons.nth(1).click()
  await expect(page.locator('html')).toHaveAttribute(
    'data-theme',
    initialTheme === 'dark' ? 'light' : 'dark',
  )
  await headerButtons.nth(1).click()
  await expect(page.locator('html')).toHaveAttribute(
    'data-theme',
    initialTheme ?? 'light',
  )
  await page.waitForTimeout(200)

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
      expectedHeader: tokenColor(
        '--device-list-header-background',
        'background',
      ),
      expectedBottom: tokenColor(
        '--visual-v2-bottom-nav-background',
        'background',
      ),
      activeColor: style('.van-tabbar-item--active').color,
      inactiveColor: style('.van-tabbar-item:not(.van-tabbar-item--active)')
        .color,
      expectedActive: tokenColor(
        '--visual-v2-bottom-nav-active-color',
        'color',
      ),
      expectedInactive: tokenColor(
        '--visual-v2-bottom-nav-inactive-color',
        'color',
      ),
      brandFontSize: style('.mobile-page-header__title').fontSize,
      expectedBrandFontSize: root
        .getPropertyValue('--device-list-title-size')
        .trim(),
    }
  })
  expect(chromeVisual).toEqual({
    headerBackground: chromeVisual.expectedHeader,
    bottomBackground: chromeVisual.expectedBottom,
    expectedHeader: chromeVisual.expectedHeader,
    expectedBottom: chromeVisual.expectedBottom,
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

  const bottomNavigationGeometry = await page.evaluate(() => {
    const nav = document.querySelector<HTMLElement>(
      '[data-testid="mobile-bottom-navigation"]',
    )!
    const footer = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-bottom"]',
    )!
    const main = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-main"]',
    )!
    const items = Array.from(
      nav.querySelectorAll<HTMLElement>('.van-tabbar-item'),
    )
    const boxes = items.map((item) => item.getBoundingClientRect())
    const iconBoxes = items.map((item) =>
      item
        .querySelector<HTMLElement>('.van-tabbar-item__icon')!
        .getBoundingClientRect(),
    )
    const labelBoxes = items.map((item) =>
      item
        .querySelector<HTMLElement>('.van-tabbar-item__text')!
        .getBoundingClientRect(),
    )
    const navBox = nav.getBoundingClientRect()
    const footerBox = footer.getBoundingClientRect()
    const mainBox = main.getBoundingClientRect()
    const expectedHeight = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--layout-bottom-nav-height',
      ),
    )
    const expectedPaddingX = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--visual-v2-bottom-nav-padding-x',
      ),
    )
    const safeAreaLeft = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-left',
      ),
    )
    const safeAreaRight = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-right',
      ),
    )
    return {
      navHeight: navBox.height,
      expectedHeight,
      equalWidth:
        Math.max(...boxes.map((box) => box.width)) -
          Math.min(...boxes.map((box) => box.width)) <=
        1,
      fillsInsetTrack:
        Math.abs(
          boxes[0]!.left -
            navBox.left -
            Math.max(expectedPaddingX, safeAreaLeft),
        ) <= 1 &&
        Math.abs(
          navBox.right -
            boxes.at(-1)!.right -
            Math.max(expectedPaddingX, safeAreaRight),
        ) <= 1,
      touchTargets: boxes.every((box) => box.height >= 44),
      iconsAboveLabels: iconBoxes.every(
        (icon, index) => icon.bottom <= labelBoxes[index]!.top,
      ),
      iconSizes: iconBoxes.map((box) => box.width),
      singleLine: items.every((item) => item.scrollWidth <= item.clientWidth),
      shellOwned: footer.contains(nav),
      mainBeforeFooter: mainBox.bottom <= footerBox.top,
      navNotFixed: getComputedStyle(nav).position !== 'fixed',
    }
  })
  expect(
    Math.abs(
      bottomNavigationGeometry.navHeight -
        bottomNavigationGeometry.expectedHeight,
    ),
  ).toBeLessThanOrEqual(1)
  expect(bottomNavigationGeometry.equalWidth).toBe(true)
  expect(bottomNavigationGeometry.fillsInsetTrack).toBe(true)
  expect(bottomNavigationGeometry.touchTargets).toBe(true)
  expect(bottomNavigationGeometry.iconsAboveLabels).toBe(true)
  expect(
    bottomNavigationGeometry.iconSizes.every(
      (size) => size >= 24 && size <= 26,
    ),
  ).toBe(true)
  expect(bottomNavigationGeometry.singleLine).toBe(true)
  expect(bottomNavigationGeometry.shellOwned).toBe(true)
  expect(bottomNavigationGeometry.mainBeforeFooter).toBe(true)
  expect(bottomNavigationGeometry.navNotFixed).toBe(true)

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
  await expect(page.getByText('功能建设中', { exact: true })).toBeVisible()
  await expect(
    page.locator('.van-tabbar-item--active').getByText('计划', {
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('tab', { name: /店铺/ }).click()
  await expect(page).toHaveURL(/#\/shops$/)
  await expect(page.getByText('功能建设中', { exact: true })).toBeVisible()
  await expect(
    page.locator('.van-tabbar-item--active').getByText('店铺', {
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('tab', { name: /我的/ }).click()
  await expect(page).toHaveURL(/#\/me$/)
  await expect(page.getByText('功能建设中', { exact: true })).toBeVisible()
  await expect(
    page.locator('.van-tabbar-item--active').getByText('我的', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/管理员|假账号|假昵称/)

  await page.getByRole('button', { name: '通知' }).click()
  await expect(page.locator('.van-toast')).toContainText('功能建设中')

  await page.goto('/#/__foundation')
  await expect(page).toHaveURL(/#\/__foundation$/)
  await page.getByRole('button', { name: '深色' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page).toHaveURL(/#\/__foundation$/)
  await expect(page.getByRole('button', { name: '返回' })).toBeVisible()

  const detailHeaderVisual = await page.evaluate(() => {
    const navBar = document.querySelector<HTMLElement>(
      '[data-testid="mobile-detail-header"]',
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

test('System快速切换与Reduced Motion不影响触控操作', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' })
  await installShellReadOnlyApi(page)
  await page.goto('/#/devices')

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  const themeButton = page.getByTestId('theme-toggle')
  await expect(themeButton).toHaveAttribute('aria-label', '切换到浅色主题')

  const transitionDuration = await themeButton.evaluate(
    (element) => window.getComputedStyle(element).transitionDuration,
  )
  expect(['0.01ms', '1e-05s']).toContain(transitionDuration.split(',')[0])

  await themeButton.click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.localStorage.getItem('control-center.mobile.theme-mode'),
      ),
    )
    .toBe('light')

  const card = page.getByTestId('device-card').first()
  const cardAction = card.getByRole('button', { name: /查看设备/ })
  const cardActionBox = await cardAction.boundingBox()
  if (!cardActionBox) throw new Error('未找到Reduced Motion设备触控区域')
  await page.mouse.move(
    cardActionBox.x + cardActionBox.width / 2,
    cardActionBox.y + cardActionBox.height / 2,
  )
  await page.mouse.down()
  await expect
    .poll(() =>
      card.evaluate((element) => window.getComputedStyle(element).transform),
    )
    .toBe('none')
  await page.mouse.move(0, 0)
  await page.mouse.up()

  await page.getByRole('button', { name: '通知' }).click()
  await expect(page.locator('.van-toast')).toContainText('功能建设中')
  expect(consoleErrors).toEqual([])
})
