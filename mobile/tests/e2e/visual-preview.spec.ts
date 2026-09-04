import { expect, test, type Page } from '@playwright/test'

import { installAuthenticatedMobileSession } from './auth-api-fixture'

const viewportWidths = [360, 375, 390, 430] as const
const themes = ['light', 'dark'] as const

function observePage(page: Page) {
  const consoleErrors: string[] = []
  const consoleInfo: string[] = []
  const apiRequests: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
    if (message.type() === 'info') consoleInfo.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    const isAuthBootstrap = [
      '/api/v1/auth/me',
      '/api/v1/access/me/teams',
      '/api/v1/access-management/me/module-access',
    ].includes(path)
    if (path.startsWith('/api/') && !isAuthBootstrap) {
      apiRequests.push(request.url())
    }
  })
  return { consoleErrors, consoleInfo, apiRequests }
}

test.beforeEach(async ({ page }) => {
  await installAuthenticatedMobileSession(page)
})

async function setTheme(page: Page, theme: 'light' | 'dark'): Promise<void> {
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

async function readCapabilityLayout(page: Page) {
  return page.getByTestId('device-capability-panel').evaluate((panel) => {
    const header = panel.querySelector<HTMLElement>(
      '.device-capability-panel__header',
    )!
    const selector = panel.querySelector<HTMLElement>(
      '[data-testid="device-capability-tabs"]',
    )!
    const wrap = selector.querySelector<HTMLElement>('.van-tabs__wrap')!
    const nav = selector.querySelector<HTMLElement>('.van-tabs__nav')!
    const tabs = Array.from(selector.querySelectorAll<HTMLElement>('.van-tab'))
    const labels = Array.from(
      selector.querySelectorAll<HTMLElement>(
        '.device-capability-panel__tab-label',
      ),
    )
    const activeSurface = selector.querySelector<HTMLElement>(
      '.van-tab--active .van-tab__text',
    )!
    const list = panel.querySelector<HTMLElement>(
      '[data-testid="application-list"]',
    )!
    const rows = Array.from(
      list.querySelectorAll<HTMLElement>('[data-testid="application-row"]'),
    )
    const headerBox = header.getBoundingClientRect()
    const selectorBox = selector.getBoundingClientRect()
    const wrapBox = wrap.getBoundingClientRect()
    const navBox = nav.getBoundingClientRect()
    const listBox = list.getBoundingClientRect()
    const tabBoxes = tabs.map((tab) => tab.getBoundingClientRect())
    const activeBox = activeSurface.getBoundingClientRect()
    const within = (child: DOMRect, parent: DOMRect) =>
      child.top >= parent.top - 1 &&
      child.right <= parent.right + 1 &&
      child.bottom <= parent.bottom + 1 &&
      child.left >= parent.left - 1

    return {
      headerBeforeSelector: headerBox.bottom <= selectorBox.top,
      selectorBeforeRows: selectorBox.bottom <= listBox.top,
      headerOutsideRows: !list.contains(header),
      selectorOutsideRows: !list.contains(selector),
      navContained: within(navBox, wrapBox),
      tabsContained: tabBoxes.every((tab) => within(tab, wrapBox)),
      activeSurfaceContained: within(activeBox, wrapBox),
      selectorHasNoInternalOverflow:
        selector.scrollHeight <= selector.clientHeight &&
        selector.scrollWidth <= selector.clientWidth,
      sameRow: tabBoxes[0]!.y === tabBoxes[1]!.y,
      equalWidth: Math.abs(tabBoxes[0]!.width - tabBoxes[1]!.width) <= 1,
      touchHeights: tabBoxes.map((tab) => tab.height),
      labelsSingleLine: labels.every(
        (label) => label.scrollHeight <= label.clientHeight,
      ),
      fiveRowsVisible: rows
        .slice(0, 5)
        .every(
          (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
        ),
      sixthRequiresScroll:
        rows[5]!.getBoundingClientRect().top >= listBox.bottom - 1 &&
        rows[5]!.getBoundingClientRect().bottom > listBox.bottom + 1,
    }
  })
}

async function readGlobalHeaderAnatomy(page: Page) {
  return page.evaluate(() => {
    const header = document.querySelector<HTMLElement>(
      '[data-testid="mobile-global-header"]',
    )!
    const shellHeader = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-header"]',
    )!
    const headline = header.querySelector<HTMLElement>(
      '.mobile-global-header__brand, .mobile-page-header__title',
    )!
    const actions = header.querySelector<HTMLElement>(
      '.mobile-global-header__actions, .mobile-page-header__actions',
    )!
    const buttons = Array.from(
      actions.querySelectorAll<HTMLButtonElement>('button'),
    )
    const icons = Array.from(
      actions.querySelectorAll<HTMLElement>('.mobile-header-icon'),
    )
    const headerBox = header.getBoundingClientRect()
    const headlineBox = headline.getBoundingClientRect()
    const actionsBox = actions.getBoundingClientRect()
    const buttonBoxes = buttons.map((button) => button.getBoundingClientRect())
    const rootStyle = window.getComputedStyle(document.documentElement)

    return {
      brandText: headline.textContent?.trim() ?? '',
      isPageHeader: header.classList.contains('mobile-global-header--page'),
      headerHeight: headerBox.height,
      expectedHeaderHeight: Number.parseFloat(
        rootStyle.getPropertyValue(
          header.classList.contains('mobile-global-header--page')
            ? '--device-list-header-height'
            : '--layout-header-height',
        ),
      ),
      brandBeforeActions: headlineBox.right <= actionsBox.left,
      actionLabels: buttons.map((button) => button.getAttribute('aria-label')),
      themeBeforeBell: buttonBoxes[0]!.left < buttonBoxes[1]!.left,
      buttonSizes: buttonBoxes.map(({ width, height }) => ({ width, height })),
      buttonVisualSizes: buttons.map((button) => {
        const style = window.getComputedStyle(button, '::before')
        return {
          width: Number.parseFloat(style.width),
          height: Number.parseFloat(style.height),
        }
      }),
      actionGap: buttonBoxes[1]!.left - buttonBoxes[0]!.right,
      iconSizes: icons.map((icon) => {
        const box = icon.getBoundingClientRect()
        return { width: box.width, height: box.height }
      }),
      iconGlyphsValid: icons.every((icon) =>
        Boolean(icon.querySelector('svg.mobile-icon__glyph')),
      ),
      borderBottomWidth: window.getComputedStyle(header).borderBottomWidth,
      shellBorderBottomWidth:
        window.getComputedStyle(shellHeader).borderBottomWidth,
      boxShadow: window.getComputedStyle(header).boxShadow,
      shellBoxShadow: window.getComputedStyle(shellHeader).boxShadow,
    }
  })
}

async function expectBottomNavigation(
  page: Page,
  activeNavigation: '设备' | '任务' | '计划' | '店铺' | '我的',
) {
  const nav = page.getByTestId('mobile-bottom-navigation')
  const items = nav.locator('.van-tabbar-item')

  await expect(nav).toBeVisible()
  await expect(items).toHaveCount(5)
  await expect(items).toHaveText(['设备', '任务', '计划', '店铺', '我的'])
  await expect(
    nav.locator('.van-tabbar-item--active').getByText(activeNavigation, {
      exact: true,
    }),
  ).toBeVisible()

  const geometry = await nav.evaluate((element) => {
    const footer = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-bottom"]',
    )!
    const main = document.querySelector<HTMLElement>(
      '[data-testid="mobile-shell-main"]',
    )!
    const entries = Array.from(
      element.querySelectorAll<HTMLElement>('.van-tabbar-item'),
    )
    const boxes = entries.map((entry) => entry.getBoundingClientRect())
    const iconBoxes = entries.map((entry) =>
      entry
        .querySelector<HTMLElement>('.van-tabbar-item__icon')!
        .getBoundingClientRect(),
    )
    const labelBoxes = entries.map((entry) =>
      entry
        .querySelector<HTMLElement>('.van-tabbar-item__text')!
        .getBoundingClientRect(),
    )
    const navBox = element.getBoundingClientRect()
    const footerBox = footer.getBoundingClientRect()
    const mainBox = main.getBoundingClientRect()
    const rootStyle = getComputedStyle(document.documentElement)

    return {
      navTop: navBox.top,
      navHeight: navBox.height,
      expectedHeight: Number.parseFloat(
        rootStyle.getPropertyValue('--layout-bottom-nav-height'),
      ),
      expectedPaddingX: Number.parseFloat(
        rootStyle.getPropertyValue('--visual-v2-bottom-nav-padding-x'),
      ),
      widths: boxes.map((box) => box.width),
      touchHeights: boxes.map((box) => box.height),
      iconSizes: iconBoxes.map((box) => ({
        width: box.width,
        height: box.height,
      })),
      iconsAboveLabels: iconBoxes.every(
        (icon, index) => icon.bottom <= labelBoxes[index]!.top,
      ),
      iconsCentered: iconBoxes.every(
        (icon, index) =>
          Math.abs(
            icon.left +
              icon.width / 2 -
              (boxes[index]!.left + boxes[index]!.width / 2),
          ) <= 1,
      ),
      labelsSingleLine: entries.every((entry, index) => {
        const label = entry.querySelector<HTMLElement>(
          '.van-tabbar-item__text',
        )!
        const labelStyle = getComputedStyle(label)
        return (
          label.getClientRects().length === 1 &&
          labelStyle.whiteSpace === 'nowrap' &&
          labelBoxes[index]!.width <= boxes[index]!.width
        )
      }),
      fillsInsetTrack:
        Math.abs(
          boxes[0]!.left -
            navBox.left -
            Number.parseFloat(
              rootStyle.getPropertyValue('--visual-v2-bottom-nav-padding-x'),
            ),
        ) <= 1 &&
        Math.abs(
          navBox.right -
            boxes[boxes.length - 1]!.right -
            Number.parseFloat(
              rootStyle.getPropertyValue('--visual-v2-bottom-nav-padding-x'),
            ),
        ) <= 1,
      shellOwned: footer.contains(element),
      mainBeforeFooter: mainBox.bottom <= footerBox.top,
      navWithinFooter:
        navBox.top >= footerBox.top && navBox.bottom <= footerBox.bottom,
      navNotFixed: getComputedStyle(element).position !== 'fixed',
      noHorizontalOverflow:
        document.documentElement.scrollWidth <= window.innerWidth,
    }
  })

  expect(
    Math.max(...geometry.widths) - Math.min(...geometry.widths),
  ).toBeLessThanOrEqual(1)
  expect(geometry.touchHeights.every((height) => height >= 44)).toBe(true)
  expect(
    geometry.iconSizes.every(
      ({ width, height }) =>
        width >= 24 && width <= 26 && height >= 24 && height <= 26,
    ),
  ).toBe(true)
  expect(geometry.iconsAboveLabels).toBe(true)
  expect(geometry.iconsCentered).toBe(true)
  expect(geometry.labelsSingleLine).toBe(true)
  expect(geometry.fillsInsetTrack).toBe(true)
  expect(geometry.shellOwned).toBe(true)
  expect(geometry.mainBeforeFooter).toBe(true)
  expect(geometry.navWithinFooter).toBe(true)
  expect(geometry.navNotFixed).toBe(true)
  expect(geometry.noHorizontalOverflow).toBe(true)
  expect(
    Math.abs(geometry.navHeight - geometry.expectedHeight),
  ).toBeLessThanOrEqual(1)

  return geometry
}

async function expectSummaryStrip(page: Page) {
  const strip = page.locator('.mobile-summary-strip')
  const metrics = strip.locator('.mobile-summary-strip__item')

  await expect(strip).toBeVisible()
  await expect(metrics).toHaveCount(4)
  await expect(metrics.locator('.mobile-summary-strip__label')).toHaveText([
    '全部设备',
    '在线设备',
    '运行中',
    '离线设备',
  ])
  await expect(metrics.locator('.mobile-summary-strip__icon')).toHaveCount(0)
  await expect(strip.locator('button')).toHaveCount(4)

  const geometry = await strip.evaluate((element) => {
    const surface = element.querySelector<HTMLElement>(
      '.mobile-summary-strip__surface',
    )!
    const slots = Array.from(
      surface.querySelectorAll<HTMLElement>('.mobile-summary-strip__item'),
    )
    const slotBoxes = slots.map((slot) => slot.getBoundingClientRect())
    const numberBoxes = slots.map((slot) =>
      slot
        .querySelector<HTMLElement>('.mobile-summary-strip__value')!
        .getBoundingClientRect(),
    )
    const labelBoxes = slots.map((slot) =>
      slot
        .querySelector<HTMLElement>('.mobile-summary-strip__label')!
        .getBoundingClientRect(),
    )
    const stripBox = element.getBoundingClientRect()
    const surfaceBox = surface.getBoundingClientRect()
    const rootStyle = getComputedStyle(document.documentElement)

    const groups = slotBoxes.map((slot, index) => {
      const number = numberBoxes[index]!
      const label = labelBoxes[index]!
      const left = Math.min(number.left, label.left)
      const right = Math.max(number.right, label.right)
      const top = Math.min(number.top, label.top)
      const bottom = Math.max(number.bottom, label.bottom)
      return {
        horizontalCenterDelta:
          (left + right) / 2 - (slot.left + slot.right) / 2,
        verticalCenterDelta: (top + bottom) / 2 - (slot.top + slot.bottom) / 2,
        elementsCentered: [number, label].every(
          (box) =>
            Math.abs(box.left + box.width / 2 - (slot.left + slot.width / 2)) <=
            0.5,
        ),
        verticalOrder: number.bottom <= label.top,
      }
    })

    const separators = slots.slice(1).map((slot) => {
      const style = getComputedStyle(slot, '::before')
      return {
        width: Number.parseFloat(style.width),
        height: Number.parseFloat(style.height),
        top: Number.parseFloat(style.top),
      }
    })

    return {
      stripTop: stripBox.top,
      stripHeight: stripBox.height,
      expectedStripHeight: Number.parseFloat(
        rootStyle.getPropertyValue('--device-list-summary-height'),
      ),
      surfaceCount: element.querySelectorAll('.mobile-summary-strip__surface')
        .length,
      surfaceContainsAllSlots: slots.every(
        (slot) => slot.parentElement === surface,
      ),
      surfaceHeight: surfaceBox.height,
      surfaceTopBreathing: Math.min(
        ...numberBoxes.map((number) => number.top - surfaceBox.top),
      ),
      surfaceBottomBreathing: Math.min(
        ...labelBoxes.map((label) => surfaceBox.bottom - label.bottom),
      ),
      slotWidths: slotBoxes.map((slot) => slot.width),
      slotTops: slotBoxes.map((slot) => slot.top),
      slotHeights: slotBoxes.map((slot) => slot.height),
      touchHeights: slots.map(
        (slot) =>
          slot
            .querySelector<HTMLElement>(
              '.mobile-summary-strip__metric--interactive',
            )!
            .getBoundingClientRect().height,
      ),
      groups,
      separators,
      labelsSingleLine: slots.every((slot) => {
        const label = slot.querySelector<HTMLElement>(
          '.mobile-summary-strip__label',
        )!
        return (
          label.getClientRects().length === 1 &&
          getComputedStyle(label).whiteSpace === 'nowrap'
        )
      }),
      numberEmphasized: slots.every((slot) => {
        const numberSize = Number.parseFloat(
          getComputedStyle(
            slot.querySelector<HTMLElement>('.mobile-summary-strip__value')!,
          ).fontSize,
        )
        const labelSize = Number.parseFloat(
          getComputedStyle(
            slot.querySelector<HTMLElement>('.mobile-summary-strip__label')!,
          ).fontSize,
        )
        return numberSize > labelSize
      }),
      buttonSemantics: slots.every(
        (slot) =>
          slot.querySelector('.mobile-summary-strip__metric')?.tagName ===
          'BUTTON',
      ),
      noHorizontalOverflow:
        surface.scrollWidth <= surface.clientWidth &&
        document.documentElement.scrollWidth <= window.innerWidth,
    }
  })

  expect(geometry.surfaceCount).toBe(1)
  expect(geometry.surfaceContainsAllSlots).toBe(true)
  expect(geometry.surfaceTopBreathing).toBeGreaterThanOrEqual(6)
  expect(geometry.surfaceBottomBreathing).toBeGreaterThanOrEqual(6)
  expect(
    Math.max(...geometry.slotWidths) - Math.min(...geometry.slotWidths),
  ).toBeLessThanOrEqual(1)
  expect(new Set(geometry.slotTops.map(Math.round)).size).toBe(1)
  expect(new Set(geometry.slotHeights.map(Math.round)).size).toBe(1)
  expect(
    geometry.groups.every(
      ({ horizontalCenterDelta }) => Math.abs(horizontalCenterDelta) <= 0.5,
    ),
  ).toBe(true)
  expect(
    geometry.groups.every(
      ({ verticalCenterDelta }) => Math.abs(verticalCenterDelta) <= 0.5,
    ),
  ).toBe(true)
  expect(
    geometry.groups.every(({ elementsCentered }) => elementsCentered),
  ).toBe(true)
  expect(geometry.groups.every(({ verticalOrder }) => verticalOrder)).toBe(true)
  expect(
    geometry.separators.every(
      ({ width, height, top }) =>
        width <= 1 && height < geometry.slotHeights[0]! && top > 0,
    ),
  ).toBe(true)
  expect(geometry.labelsSingleLine).toBe(true)
  expect(geometry.numberEmphasized).toBe(true)
  expect(geometry.buttonSemantics).toBe(true)
  expect(geometry.touchHeights.every((height) => height >= 44)).toBe(true)
  expect(geometry.noHorizontalOverflow).toBe(true)
  expect(geometry.stripHeight).toBe(geometry.expectedStripHeight)

  return geometry
}

async function expectDetailHeader(
  page: Page,
  title: '设备详情' | '任务详情',
  activeNavigation: '设备' | '任务',
): Promise<void> {
  const visualV2 = true
  const header = page.getByTestId('mobile-detail-header')
  const headerTitle = page.getByTestId('mobile-detail-header-title')

  await expect(header).toBeVisible()
  await expect(headerTitle).toHaveText(title)
  await expect(header.locator('.van-icon-arrow-left')).toBeVisible()
  await expect(page.getByTestId('mobile-global-header')).toHaveCount(0)
  await expect(
    page.locator('.van-tabbar-item--active').getByText(activeNavigation, {
      exact: true,
    }),
  ).toBeVisible()

  const geometry = await header.evaluate((element, useVisualV2) => {
    const backButton = element.querySelector<HTMLElement>(
      'button[aria-label="返回"]',
    )!
    const titleElement = element.querySelector<HTMLElement>(
      '[data-testid="mobile-detail-header-title"]',
    )!
    const rightSlot = element.querySelector<HTMLElement>(
      '[data-testid="mobile-detail-header-right"]',
    )!
    const icon = element.querySelector<HTMLElement>('.van-icon-arrow-left')!
    const rootBox = element.getBoundingClientRect()
    const backBox = backButton.getBoundingClientRect()
    const titleBox = titleElement.getBoundingClientRect()
    const rightBox = rightSlot.getBoundingClientRect()
    const rootStyle = window.getComputedStyle(element)
    const titleStyle = window.getComputedStyle(titleElement)
    const documentStyle = window.getComputedStyle(document.documentElement)

    return {
      height: rootBox.height,
      expectedHeight: Number.parseFloat(
        documentStyle.getPropertyValue(
          useVisualV2
            ? '--visual-v2-detail-header-height'
            : '--layout-detail-header-height',
        ),
      ),
      backWidth: backBox.width,
      backHeight: backBox.height,
      iconSize: Number.parseFloat(window.getComputedStyle(icon).fontSize),
      expectedIconSize: Number.parseFloat(
        documentStyle.getPropertyValue(
          useVisualV2
            ? '--visual-v2-detail-header-icon-size'
            : '--icon-size-default',
        ),
      ),
      titleCenterDelta:
        titleBox.left + titleBox.width / 2 - (rootBox.left + rootBox.width / 2),
      leftSlotWidth: backBox.width,
      rightSlotWidth: rightBox.width,
      leftInset: backBox.left - rootBox.left,
      rightInset: rootBox.right - rightBox.right,
      titleFontSize: titleStyle.fontSize,
      expectedTitleFontSize: documentStyle
        .getPropertyValue(
          useVisualV2
            ? '--typography-v2-detail-title-size'
            : '--font-size-title',
        )
        .trim(),
      titleLineHeight: titleStyle.lineHeight,
      expectedTitleLineHeight: documentStyle
        .getPropertyValue(
          useVisualV2
            ? '--typography-v2-detail-title-line-height'
            : '--line-height-title',
        )
        .trim(),
      borderBottomWidth: rootStyle.borderBottomWidth,
      boxShadow: rootStyle.boxShadow,
    }
  }, visualV2)

  expect(geometry.height).toBe(geometry.expectedHeight)
  expect(geometry.backWidth).toBeGreaterThanOrEqual(44)
  expect(geometry.backHeight).toBeGreaterThanOrEqual(44)
  expect(geometry.iconSize).toBe(geometry.expectedIconSize)
  expect(Math.abs(geometry.titleCenterDelta)).toBeLessThanOrEqual(0.5)
  expect(geometry.leftSlotWidth).toBe(geometry.rightSlotWidth)
  expect(
    Math.abs(geometry.leftInset - geometry.rightInset),
  ).toBeLessThanOrEqual(0.5)
  expect(geometry.titleFontSize).toBe(geometry.expectedTitleFontSize)
  expect(geometry.titleLineHeight).toBe(geometry.expectedTitleLineHeight)
  expect(geometry.borderBottomWidth).toBe('0px')
  expect(geometry.boxShadow).toBe('none')
  if (title === '设备详情') {
    await expect(page.getByRole('button', { name: '更多信息' })).toBeVisible()
  }
  await expect(page.getByTestId('mobile-shell-bottom')).toBeVisible()
  await expectNoHorizontalOverflow(page)
}

for (const width of viewportWidths) {
  for (const theme of themes) {
    test(`Visual Mock ${width}px ${theme} 稳定展示设备与任务`, async ({
      page,
    }, testInfo) => {
      test.setTimeout(60_000)
      const observation = observePage(page)
      await page.setViewportSize({ width, height: 844 })
      await setTheme(page, theme)
      await page.goto('/#/devices')

      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.getByTestId('device-card')).toHaveCount(20)
      await expect(page.getByTestId('summary-all')).toHaveText('20')
      await expect(page.getByTestId('summary-online')).toHaveText('8')
      await expect(page.getByTestId('summary-running')).toHaveText('1')
      await expect(page.getByTestId('summary-offline')).toHaveText('12')
      await expect(page.getByTestId('device-search')).toBeEnabled()
      await expect(page.getByTestId('summary-metric-all')).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)
      await expect(page.getByText('没有设备', { exact: true })).toHaveCount(0)
      const summaryGeometry = await expectSummaryStrip(page)
      const onlineMetric = page.getByTestId('summary-metric-online')
      await expect(onlineMetric).toHaveAttribute('aria-pressed', 'false')
      await onlineMetric.click()
      await expect(onlineMetric).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByTestId('device-card')).toHaveCount(8)
      await onlineMetric.click()
      await expect(onlineMetric).toHaveAttribute('aria-pressed', 'false')
      await expect(page.getByTestId('summary-metric-all')).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      await expect(page.getByTestId('device-card')).toHaveCount(20)

      if (width === 390 && theme === 'light') {
        await page.getByTestId('summary-metric-offline').click()
        await expect(
          page.getByTestId('summary-metric-offline'),
        ).toHaveAttribute('aria-pressed', 'true')
        await expect(page.getByTestId('device-card')).toHaveCount(12)
        await page.getByTestId('summary-metric-offline').click()
        await expect(page.getByTestId('device-card')).toHaveCount(20)

        await page.getByTestId('device-search').fill('客服自动化')
        await expect(page.getByTestId('device-card')).toHaveCount(1)
        await expect(page.getByTestId('device-card-name')).toHaveText(
          '客服自动化工作站（华东售后协同中心）',
        )
        await page.getByTestId('device-search').fill('')
        await expect(page.getByTestId('device-card')).toHaveCount(20)
      }

      const deviceTypography = await page.evaluate(() => {
        const read = (selector: string) => {
          const style = window.getComputedStyle(
            document.querySelector<HTMLElement>(selector)!,
          )
          return `${style.fontSize}/${style.fontWeight}`
        }
        return {
          brand: read('.mobile-page-header__title'),
          cardTitle: read('[data-testid="device-card-name"]'),
          summaryNumber: read('.mobile-summary-strip__value'),
          meta: read('.device-list-card__meta'),
        }
      })
      expect(deviceTypography).toEqual({
        brand: '20px/600',
        cardTitle: '16.5px/600',
        summaryNumber: '23px/600',
        meta: '13px/400',
      })

      const visualDeviceCards = page.getByTestId('device-card')
      await expect(
        visualDeviceCards.nth(0).getByTestId('device-card-runtime'),
      ).toHaveText('运行中')
      await expect(
        visualDeviceCards.nth(1).getByTestId('device-card-runtime'),
      ).toHaveText('在线')
      await expect(
        visualDeviceCards.nth(2).getByTestId('device-card-runtime'),
      ).toHaveText('在线')
      await expect(
        visualDeviceCards.nth(2).getByTestId('device-card-meta'),
      ).toContainText('已停用')
      await expect(
        visualDeviceCards.nth(3).getByTestId('device-card-runtime'),
      ).toHaveText('离线')
      await expect(
        visualDeviceCards.nth(3).getByTestId('device-card-name'),
      ).toHaveText('客服自动化工作站（华东售后协同中心）')
      const deviceCardHeights = await visualDeviceCards.evaluateAll((cards) =>
        cards.slice(0, 5).map((card) => card.getBoundingClientRect().height),
      )
      expect(new Set(deviceCardHeights.map(Math.round)).size).toBe(1)
      const deviceCardSpacing = await visualDeviceCards.evaluateAll((cards) =>
        cards.slice(0, 2).map((card, index, visibleCards) => {
          const style = window.getComputedStyle(card)
          const next = visibleCards[index + 1]
          return {
            paddingTop: style.paddingTop,
            paddingRight: style.paddingRight,
            paddingBottom: style.paddingBottom,
            paddingLeft: style.paddingLeft,
            columnGap: style.columnGap,
            cardGap: next
              ? Math.round(
                  next.getBoundingClientRect().top -
                    card.getBoundingClientRect().bottom,
                )
              : null,
          }
        }),
      )
      expect(deviceCardSpacing).toEqual([
        {
          paddingTop: '15px',
          paddingRight: '17px',
          paddingBottom: '15px',
          paddingLeft: '16px',
          columnGap: 'normal',
          cardGap: 14,
        },
        {
          paddingTop: '15px',
          paddingRight: '17px',
          paddingBottom: '15px',
          paddingLeft: '16px',
          columnGap: 'normal',
          cardGap: null,
        },
      ])
      const primaryLeadingVisualTokens = await page.evaluate(() => {
        const rootStyle = window.getComputedStyle(document.documentElement)
        return {
          slot: Number.parseFloat(
            rootStyle.getPropertyValue('--device-list-card-artwork-column'),
          ),
          artwork: Number.parseFloat(
            rootStyle.getPropertyValue('--device-list-artwork-width'),
          ),
        }
      })
      const deviceLeadingVisuals = await visualDeviceCards.evaluateAll(
        (cards) =>
          cards.slice(0, 5).map((card) => {
            const leading = card.querySelector<HTMLElement>(
              '[data-testid="device-card-leading"]',
            )!
            const artwork = leading.querySelector<HTMLElement>(
              '[data-testid="device-status-artwork"]',
            )!
            return {
              slotWidth: leading.getBoundingClientRect().width,
              artworkWidth: artwork.getBoundingClientRect().width,
            }
          }),
      )
      expect(
        deviceLeadingVisuals.every(
          (visual) =>
            Math.abs(visual.slotWidth - primaryLeadingVisualTokens.slot) <= 1 &&
            visual.artworkWidth === primaryLeadingVisualTokens.artwork &&
            visual.artworkWidth < visual.slotWidth,
        ),
      ).toBe(true)

      const headerVisual = await page.evaluate(() => {
        const header = document.querySelector<HTMLElement>(
          '[data-testid="mobile-shell-header"]',
        )!
        const buttons = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.mobile-page-header__actions .mobile-icon-button',
          ),
        )
        const buttonStyles = buttons.map((button) => {
          const box = button.getBoundingClientRect()
          const surface = window.getComputedStyle(button, '::before')
          return {
            width: box.width,
            height: box.height,
            background: surface.backgroundColor,
            shadow: surface.boxShadow,
          }
        })
        const headerStyle = window.getComputedStyle(header)
        return {
          borderBottomWidth: headerStyle.borderBottomWidth,
          boxShadow: headerStyle.boxShadow,
          buttonStyles,
          iconGlyphs: Array.from(
            document.querySelectorAll<HTMLElement>(
              '.mobile-page-header__actions .mobile-header-icon',
            ),
          ).map((icon) => {
            const box = icon.getBoundingClientRect()
            return {
              key: icon.dataset.iconKey,
              role: icon.dataset.iconRole,
              glyph: Boolean(icon.querySelector('svg.mobile-icon__glyph')),
              width: box.width,
              height: box.height,
            }
          }),
        }
      })
      expect(headerVisual.borderBottomWidth).toBe('0px')
      expect(headerVisual.boxShadow).toBe('none')
      expect(headerVisual.buttonStyles).toHaveLength(2)
      expect(headerVisual.buttonStyles[0]).toEqual(headerVisual.buttonStyles[1])
      expect(headerVisual.buttonStyles[0]?.width).toBeGreaterThanOrEqual(44)
      expect(headerVisual.iconGlyphs).toHaveLength(2)
      expect(headerVisual.iconGlyphs.map((icon) => icon.key)).toEqual([
        theme === 'dark' ? 'theme-light' : 'theme-dark',
        'notification-bell',
      ])
      expect(
        headerVisual.iconGlyphs.every(
          (icon) =>
            icon.role === 'action' &&
            icon.glyph &&
            icon.width > 0 &&
            icon.height > 0,
        ),
      ).toBe(true)

      const themeButton = page.getByTestId('theme-toggle')
      const bellButton = page.getByRole('button', { name: '通知' })
      expect((await themeButton.boundingBox())!.x).toBeLessThan(
        (await bellButton.boundingBox())!.x,
      )
      const deviceGlobalHeader = await readGlobalHeaderAnatomy(page)
      expect(deviceGlobalHeader.brandText).toBe('设备')
      expect(deviceGlobalHeader.isPageHeader).toBe(true)
      expect(deviceGlobalHeader.headerHeight).toBe(
        deviceGlobalHeader.expectedHeaderHeight,
      )
      expect(deviceGlobalHeader.brandBeforeActions).toBe(true)
      expect(deviceGlobalHeader.actionLabels).toEqual([
        theme === 'dark' ? '切换到浅色主题' : '切换到深色主题',
        '通知',
      ])
      expect(deviceGlobalHeader.themeBeforeBell).toBe(true)
      expect(deviceGlobalHeader.buttonSizes).toEqual([
        { width: 45, height: 45 },
        { width: 45, height: 45 },
      ])
      expect(deviceGlobalHeader.buttonVisualSizes).toEqual([
        { width: 40, height: 40 },
        { width: 40, height: 40 },
      ])
      expect(deviceGlobalHeader.iconSizes[0]).toEqual(
        deviceGlobalHeader.iconSizes[1],
      )
      expect(deviceGlobalHeader.iconGlyphsValid).toBe(true)
      expect(deviceGlobalHeader.borderBottomWidth).toBe('0px')
      expect(deviceGlobalHeader.shellBorderBottomWidth).toBe('0px')
      expect(deviceGlobalHeader.boxShadow).toBe('none')
      expect(deviceGlobalHeader.shellBoxShadow).toBe('none')
      await expect(page.getByRole('tab')).toHaveText([
        '设备',
        '任务',
        '计划',
        '店铺',
        '我的',
      ])
      const deviceBottomNavigation = await expectBottomNavigation(page, '设备')
      const deviceListScroll = page.getByTestId('device-list-scroll')
      await deviceListScroll.evaluate((element) => {
        element.scrollTop = 240
      })
      await expect
        .poll(async () => {
          const currentTop = await page
            .getByTestId('mobile-bottom-navigation')
            .evaluate((element) => element.getBoundingClientRect().top)
          return Math.abs(currentTop - deviceBottomNavigation.navTop)
        })
        .toBeLessThanOrEqual(0.5)
      await expect
        .poll(async () => {
          const currentTop = await page
            .locator('.mobile-summary-strip')
            .evaluate((element) => element.getBoundingClientRect().top)
          return Math.abs(currentTop - summaryGeometry.stripTop)
        })
        .toBeLessThanOrEqual(0.5)
      await deviceListScroll.evaluate((element) => {
        element.scrollTop = 0
      })
      await expectNoHorizontalOverflow(page)
      expect(
        await page.evaluate(() => {
          const style = (selector: string) =>
            window.getComputedStyle(
              document.querySelector<HTMLElement>(selector)!,
            )
          const scroll = document.querySelector<HTMLElement>(
            '[data-testid="device-list-scroll"]',
          )!
          return {
            summaryHeight: style('.mobile-summary-strip').height,
            summaryStacked: Array.from(
              document.querySelectorAll<HTMLElement>(
                '.mobile-summary-strip__item',
              ),
            ).every((item) => {
              const value = item.querySelector<HTMLElement>(
                '.mobile-summary-strip__value',
              )!
              const label = item.querySelector<HTMLElement>(
                '.mobile-summary-strip__label',
              )!
              const valueBox = value.getBoundingClientRect()
              const labelBox = label.getBoundingClientRect()
              return valueBox.bottom <= labelBox.top
            }),
            controlsHeight: style('[data-testid="device-list-controls"]')
              .height,
            searchHeight: style('.mobile-search-field').height,
            scrollbarWidth: style('[data-testid="device-list-scroll"]')
              .scrollbarWidth,
            scrollable: scroll.scrollHeight > scroll.clientHeight,
            documentScrollTop: document.scrollingElement?.scrollTop ?? 0,
          }
        }),
      ).toEqual({
        summaryHeight: '90px',
        summaryStacked: true,
        controlsHeight: '148px',
        searchHeight: '44px',
        scrollbarWidth: 'none',
        scrollable: true,
        documentScrollTop: 0,
      })

      if (width === 390 || (width === 360 && theme === 'light')) {
        await page.screenshot({
          path: testInfo.outputPath(
            `mobile-summary-strip-device-${width}-${theme}.png`,
          ),
          clip: { x: 0, y: 0, width, height: 300 },
        })
      }

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`visual-device-390-${theme}.png`),
        })
        await page.screenshot({
          path: testInfo.outputPath(
            `mobile-bottom-navigation-device-list-390-${theme}.png`,
          ),
        })
        await page.screenshot({
          path: testInfo.outputPath(
            `mobile-global-header-device-390-${theme}.png`,
          ),
          clip: { x: 0, y: 0, width: 390, height: 260 },
        })
      }
      if ((width === 360 || width === 430) && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath(`visual-device-${width}-light.png`),
        })
      }

      await page
        .getByRole('button', { name: '查看设备：运营', exact: true })
        .click()
      await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
      await expectDetailHeader(page, '设备详情', '设备')
      const deviceDetailBottomNavigation = await expectBottomNavigation(
        page,
        '设备',
      )
      const detailHero = page.getByTestId('device-detail-hero')
      await expect(detailHero.getByTestId('device-hero-name')).toHaveText(
        '运营',
      )
      await expect(detailHero.getByTestId('device-hero-status')).toHaveText(
        '运行中',
      )
      await expect(
        detailHero.getByTestId('device-hero-heartbeat'),
      ).toContainText('最后心跳：')
      await expect(detailHero.getByTestId('device-hero-meta')).toContainText(
        'Worker 0.4.6',
      )
      await expect(detailHero.getByTestId('device-hero-meta')).toContainText(
        '影刀 6.3.6',
      )
      await expect(
        detailHero.getByTestId('device-status-artwork'),
      ).toHaveAttribute('data-device-artwork-variant', 'hero')
      await expect(
        detailHero.getByTestId('device-status-artwork'),
      ).toHaveAttribute('data-device-artwork-state', 'running')
      await expect(page.getByTestId('device-capability-panel')).toBeVisible()
      await expect(page.getByTestId('application-list')).toHaveCSS(
        'scrollbar-width',
        'none',
      )
      const capabilitySelector = await readCapabilityLayout(page)
      expect(capabilitySelector).toMatchObject({
        headerBeforeSelector: true,
        selectorBeforeRows: true,
        headerOutsideRows: true,
        selectorOutsideRows: true,
        tabsContained: true,
        activeSurfaceContained: true,
        selectorHasNoInternalOverflow: true,
        sameRow: true,
        equalWidth: true,
        labelsSingleLine: true,
        fiveRowsVisible: true,
        sixthRequiresScroll: true,
      })
      expect(
        capabilitySelector.touchHeights.every((height) => height >= 44),
      ).toBe(true)
      const heroGeometry = await detailHero.evaluate((hero) => {
        const root = hero.getBoundingClientRect()
        const artwork = hero
          .querySelector<HTMLElement>('.device-detail-hero__artwork')!
          .getBoundingClientRect()
        const content = hero
          .querySelector<HTMLElement>('.device-detail-hero__content')!
          .getBoundingClientRect()
        const name = hero.querySelector<HTMLElement>(
          '[data-testid="device-hero-name"]',
        )!
        const nameStyle = window.getComputedStyle(name)
        const rootStyle = window.getComputedStyle(hero)
        const documentStyle = window.getComputedStyle(document.documentElement)
        return {
          minHeight: Number.parseFloat(rootStyle.minHeight),
          expectedMinHeight: Number.parseFloat(
            documentStyle.getPropertyValue(
              '--visual-v2-detail-hero-min-height',
            ),
          ),
          artworkBeforeContent: artwork.right <= content.left,
          nameOverflow: nameStyle.overflow,
          nameTextOverflow: nameStyle.textOverflow,
          nameWhiteSpace: nameStyle.whiteSpace,
          titleSize: nameStyle.fontSize,
          expectedTitleSize: documentStyle
            .getPropertyValue('--typography-v2-detail-hero-title-size')
            .trim(),
          fitsViewport: root.left >= 0 && root.right <= window.innerWidth + 1,
        }
      })
      expect(heroGeometry).toEqual({
        minHeight: heroGeometry.expectedMinHeight,
        expectedMinHeight: heroGeometry.expectedMinHeight,
        artworkBeforeContent: true,
        nameOverflow: 'hidden',
        nameTextOverflow: 'ellipsis',
        nameWhiteSpace: 'nowrap',
        titleSize: heroGeometry.expectedTitleSize,
        expectedTitleSize: heroGeometry.expectedTitleSize,
        fitsViewport: true,
      })
      await expect(page.locator('.device-runtime-summary')).toHaveCount(0)
      await expect(page.locator('.van-tabbar-item')).toHaveText([
        '设备',
        '任务',
        '计划',
        '店铺',
        '我的',
      ])
      const deviceDetailScroll = page.getByRole('region', {
        name: '设备详情内容',
      })
      await deviceDetailScroll.evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
      await expect
        .poll(async () => {
          const currentTop = await page
            .getByTestId('mobile-bottom-navigation')
            .evaluate((element) => element.getBoundingClientRect().top)
          return Math.abs(currentTop - deviceDetailBottomNavigation.navTop)
        })
        .toBeLessThanOrEqual(0.5)
      await deviceDetailScroll.evaluate((element) => {
        element.scrollTop = 0
      })
      if (
        width === 390 ||
        (theme === 'light' && (width === 360 || width === 430))
      ) {
        await page.screenshot({
          path: testInfo.outputPath(
            `visual-device-detail-${width}-${theme}.png`,
          ),
        })
      }
      if (width === 390) {
        if (theme === 'light') {
          await page.screenshot({
            path: testInfo.outputPath(
              'mobile-bottom-navigation-device-detail-390-light.png',
            ),
          })
        }
        await page.screenshot({
          path: testInfo.outputPath(
            `mobile-detail-header-device-390-${theme}.png`,
          ),
        })
      }
      await expectNoHorizontalOverflow(page)

      await page.goto(
        '/#/tasks/visual-task-running?fromDeviceId=visual-device-operations',
      )
      await expect(page.getByTestId('task-detail')).toContainText('订单同步', {
        timeout: 10_000,
      })
      await expectDetailHeader(page, '任务详情', '任务')
      await expectBottomNavigation(page, '任务')
      const taskDetailDensity = await page.evaluate(() => {
        const detail = document.querySelector<HTMLElement>(
          '[aria-label="任务详情内容"]',
        )!
        const card = document.querySelector<HTMLElement>(
          '[data-testid="task-detail"]',
        )!
        const runtimeLog = document.querySelector<HTMLElement>('.runtime-log')!
        const runtimeHeading = runtimeLog.querySelector<HTMLElement>(
          '.runtime-log__heading',
        )!
        const runtimeScroll = runtimeLog.querySelector<HTMLElement>(
          '[data-testid="runtime-log-scroll"]',
        )!
        const bottom = document.querySelector<HTMLElement>(
          '[data-testid="mobile-shell-bottom"]',
        )!
        const detailBox = detail.getBoundingClientRect()
        const cardBox = card.getBoundingClientRect()
        const runtimeBox = runtimeLog.getBoundingClientRect()
        const headingBox = runtimeHeading.getBoundingClientRect()
        const bottomBox = bottom.getBoundingClientRect()

        return {
          startsAtTop: detail.scrollTop === 0 && cardBox.top >= detailBox.top,
          cardBeforeRuntime: cardBox.bottom <= runtimeBox.top,
          runtimeHeadingInViewport: headingBox.top < bottomBox.top,
          pageOverflowY: window.getComputedStyle(detail).overflowY,
          runtimeOverflowY: window.getComputedStyle(runtimeScroll).overflowY,
          headingOutsideScroll: !runtimeScroll.contains(runtimeHeading),
          documentScrollable:
            document.documentElement.scrollHeight > window.innerHeight,
        }
      })
      expect(taskDetailDensity).toEqual({
        startsAtTop: true,
        cardBeforeRuntime: true,
        runtimeHeadingInViewport: true,
        pageOverflowY: 'hidden',
        runtimeOverflowY: 'auto',
        headingOutsideScroll: true,
        documentScrollable: false,
      })
      if (width === 390 || (theme === 'light' && width === 360)) {
        await page.screenshot({
          path: testInfo.outputPath(`visual-task-detail-${width}-${theme}.png`),
        })
      }
      if (width === 390 && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath('mobile-detail-header-task-390-light.png'),
        })
      }

      await page.getByRole('button', { name: '返回' }).click()
      await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
      await expectDetailHeader(page, '设备详情', '设备')

      await page.getByRole('button', { name: '返回' }).click()
      await expect(page).toHaveURL(/#\/devices$/)
      await expect(page.getByTestId('device-card').first()).toBeVisible()

      await page.getByRole('tab', { name: /任务$/ }).click()
      await expect(page).toHaveURL(/#\/tasks$/, { timeout: 10_000 })
      await expectBottomNavigation(page, '任务')
      const taskGlobalHeader = await readGlobalHeaderAnatomy(page)
      expect(taskGlobalHeader.brandText).toBe('任务')
      expect(taskGlobalHeader.isPageHeader).toBe(true)
      expect(taskGlobalHeader.actionLabels).toEqual(
        deviceGlobalHeader.actionLabels,
      )
      expect(taskGlobalHeader.iconSizes).toEqual(deviceGlobalHeader.iconSizes)
      await expect(page.getByTestId('mobile-header-menu')).toHaveAttribute(
        'aria-label',
        '筛选运行日期',
      )
      await expect(page.getByTestId('task-card')).toHaveCount(5)
      for (const status of ['执行中', '成功', '失败', '待执行', '已丢失']) {
        await expect(
          page.getByText(status, { exact: true }).first(),
        ).toBeVisible()
      }
      await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)
      await expect(page.getByText('暂无任务', { exact: true })).toHaveCount(0)
      await expect(page.locator('.task-list-card .van-progress')).toHaveCount(0)
      await expect(page.getByText('3 / 5', { exact: true })).toHaveCount(0)
      await expect(page.getByText('8 / 12', { exact: true })).toHaveCount(0)
      await expect(
        page.getByText('正在处理 HuanYu 店铺', { exact: true }),
      ).toHaveCount(0)
      await expectNoHorizontalOverflow(page)
      await expect(page.getByTestId('mobile-list-toolbar')).toHaveCount(0)
      await expect(page.getByTestId('task-list-controls')).toBeVisible()
      await expect(page.getByTestId('mobile-list-context-card')).toHaveCSS(
        'min-height',
        '48px',
      )
      await expect(page.getByTestId('task-list-scroll')).toHaveCSS(
        'scrollbar-width',
        'none',
      )
      await expect(page.getByTestId('task-card-name').first()).toHaveCSS(
        'font-size',
        '16.5px',
      )
      await expect(page.getByTestId('task-card-name').first()).toHaveCSS(
        'font-weight',
        '600',
      )
      const taskCardHeights = await page
        .getByTestId('task-card')
        .evaluateAll((cards) =>
          cards.map((card) => card.getBoundingClientRect().height),
        )
      expect(new Set(taskCardHeights.map(Math.round)).size).toBe(1)
      const taskCardSpacing = await page
        .getByTestId('task-card')
        .evaluateAll((cards) =>
          cards.slice(0, 2).map((card, index, visibleCards) => {
            const style = window.getComputedStyle(card)
            const next = visibleCards[index + 1]
            return {
              paddingTop: style.paddingTop,
              paddingRight: style.paddingRight,
              paddingBottom: style.paddingBottom,
              paddingLeft: style.paddingLeft,
              columnGap: style.columnGap,
              cardGap: next
                ? Math.round(
                    next.getBoundingClientRect().top -
                      card.getBoundingClientRect().bottom,
                  )
                : null,
            }
          }),
        )
      const taskCardTokens = await page.evaluate(() => {
        const rootStyle = window.getComputedStyle(document.documentElement)
        return {
          paddingTop: rootStyle
            .getPropertyValue('--visual-v2-business-card-padding-top')
            .trim(),
          paddingRight: rootStyle
            .getPropertyValue('--visual-v2-business-card-padding-right')
            .trim(),
          paddingBottom: rootStyle
            .getPropertyValue('--visual-v2-business-card-padding-bottom')
            .trim(),
          paddingLeft: rootStyle
            .getPropertyValue('--visual-v2-business-card-padding-left')
            .trim(),
          leadingColumn: Number.parseFloat(
            rootStyle.getPropertyValue(
              '--visual-v2-business-card-leading-column',
            ),
          ),
          artwork: Number.parseFloat(
            rootStyle.getPropertyValue('--visual-v2-task-artwork-size'),
          ),
          icon: Number.parseFloat(
            rootStyle.getPropertyValue('--visual-v2-task-artwork-icon-size'),
          ),
        }
      })
      expect(taskCardSpacing).toEqual([
        {
          paddingTop: taskCardTokens.paddingTop,
          paddingRight: taskCardTokens.paddingRight,
          paddingBottom: taskCardTokens.paddingBottom,
          paddingLeft: taskCardTokens.paddingLeft,
          columnGap: 'normal',
          cardGap: 14,
        },
        {
          paddingTop: taskCardTokens.paddingTop,
          paddingRight: taskCardTokens.paddingRight,
          paddingBottom: taskCardTokens.paddingBottom,
          paddingLeft: taskCardTokens.paddingLeft,
          columnGap: 'normal',
          cardGap: null,
        },
      ])
      const taskLeadingVisuals = await page
        .getByTestId('task-card')
        .evaluateAll((cards) =>
          cards.map((card) => {
            const slot = card.querySelector<HTMLElement>(
              '[data-testid="business-card-leading"]',
            )!
            const leading = card.querySelector<HTMLElement>(
              '[data-testid="task-card-leading"]',
            )!
            const icon = leading.querySelector<HTMLElement>('.mobile-icon')!
            return {
              slotWidth: slot.getBoundingClientRect().width,
              artworkSize: leading.getBoundingClientRect().width,
              iconSize: icon.getBoundingClientRect().width,
            }
          }),
        )
      expect(
        taskLeadingVisuals.every(
          (visual) =>
            Math.abs(visual.slotWidth - taskCardTokens.leadingColumn) <= 1 &&
            visual.artworkSize === taskCardTokens.artwork &&
            visual.iconSize === taskCardTokens.icon &&
            visual.iconSize < visual.artworkSize &&
            visual.artworkSize < visual.slotWidth,
        ),
      ).toBe(true)

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`visual-task-390-${theme}.png`),
        })
      }
      if (width === 360 && theme === 'light') {
        await page.screenshot({
          path: testInfo.outputPath('visual-task-360-light.png'),
        })
      }

      expect(observation.apiRequests).toEqual([])
      expect(observation.consoleErrors).toEqual([])
      expect(
        observation.consoleInfo.some((message) =>
          message.includes('Mock DataSource enabled'),
        ),
      ).toBe(true)
    })
  }
}

for (const fixture of [
  { width: 390, theme: 'light', file: 'device-detail-hero-390-light.png' },
  { width: 360, theme: 'light', file: 'device-detail-hero-360-light.png' },
  { width: 390, theme: 'dark', file: 'device-detail-hero-390-dark.png' },
] as const) {
  test(`DeviceDetailHero ${fixture.width}px ${fixture.theme} 保持真实状态与响应式结构`, async ({
    page,
  }, testInfo) => {
    const observation = observePage(page)
    await page.setViewportSize({ width: fixture.width, height: 844 })
    await setTheme(page, fixture.theme)
    await page.goto('/#/devices/visual-device-support')

    const hero = page.getByTestId('device-detail-hero')
    await expect(hero).toBeVisible()
    await expect(hero.getByTestId('device-hero-name')).toHaveText('售后')
    await expect(hero.getByTestId('device-hero-status')).toHaveText('在线')
    await expect(hero.getByTestId('device-hero-heartbeat')).toContainText(
      '最后心跳：',
    )
    await expect(hero.getByTestId('device-hero-meta')).toContainText(
      'Worker 0.4.6',
    )
    await expect(hero.getByTestId('device-hero-meta')).toContainText(
      '影刀 6.3.6',
    )
    await expect(hero).not.toContainText(/HuanYu001|Provider|GY00099|5\.36\.1/)

    const anatomy = await hero.evaluate((root) => {
      const rootBox = root.getBoundingClientRect()
      const artwork = root
        .querySelector<HTMLElement>('.device-detail-hero__artwork')!
        .getBoundingClientRect()
      const content = root
        .querySelector<HTMLElement>('.device-detail-hero__content')!
        .getBoundingClientRect()
      const name = root.querySelector<HTMLElement>(
        '[data-testid="device-hero-name"]',
      )!
      const nameStyle = window.getComputedStyle(name)
      const metaItems = Array.from(
        root.querySelectorAll<HTMLElement>('.device-detail-hero__meta-item'),
      )
      return {
        artworkBeforeContent: artwork.right <= content.left,
        artworkVerticallyCentered:
          Math.abs(
            artwork.top +
              artwork.height / 2 -
              (content.top + content.height / 2),
          ) <= 1,
        deviceName: {
          overflow: nameStyle.overflow,
          textOverflow: nameStyle.textOverflow,
          whiteSpace: nameStyle.whiteSpace,
        },
        metaCount: metaItems.length,
        metaSingleLine: metaItems.every(
          (item) => item.scrollHeight <= item.clientHeight,
        ),
        withinViewport:
          rootBox.left >= 0 && rootBox.right <= window.innerWidth + 1,
      }
    })
    expect(anatomy.deviceName).toEqual({
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    })
    expect(anatomy.artworkBeforeContent).toBe(true)
    expect(anatomy.artworkVerticallyCentered).toBe(true)
    expect(anatomy.metaCount).toBe(2)
    expect(anatomy.metaSingleLine).toBe(true)
    expect(anatomy.withinViewport).toBe(true)
    await expect(page.getByTestId('device-capability-panel')).toBeVisible()
    await expect(page.locator('.device-runtime-summary')).toHaveCount(0)
    await expectNoHorizontalOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(fixture.file),
      clip: { x: 0, y: 0, width: fixture.width, height: 430 },
    })

    expect(observation.apiRequests).toEqual([])
    expect(observation.consoleErrors).toEqual([])
  })
}

test('Visual Mock 复用正式设备详情与任务详情', async ({ page }, testInfo) => {
  const observation = observePage(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await setTheme(page, 'light')
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(20)

  await page
    .getByRole('button', { name: '查看设备：运营', exact: true })
    .click()
  await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
  await expect(page.getByTestId('device-detail')).toContainText('运营')
  await expect(page.getByTestId('device-hero-status')).toHaveText('运行中')
  await expect(page.getByTestId('device-hero-meta')).toContainText(
    'Worker 0.4.6',
  )
  await expect(page.getByTestId('device-hero-meta')).toContainText('影刀 6.3.6')
  await expect(page.getByTestId('device-detail-hero')).not.toContainText(
    /HuanYu001|GY00099|5\.36\.1/,
  )
  await expect(page.locator('.device-capability-panel__tab-label')).toHaveText([
    '影刀应用',
    'Skills',
  ])
  await expect(page.locator('.device-capability-panel__tab-count')).toHaveText([
    '8',
    '5',
  ])
  await expect(page.getByTestId('device-current-task')).toContainText(
    '订单同步',
  )
  await expect(
    page.getByTestId('device-current-task').getByTestId('task-card'),
  ).toBeVisible()
  await expect(
    page.getByTestId('device-current-task').getByTestId('task-card-chevron'),
  ).toBeVisible()
  await expect(
    page.getByTestId('device-current-task').locator('.van-progress'),
  ).toHaveCount(0)
  const currentTaskCardSpacing = await page
    .getByTestId('device-current-task')
    .getByTestId('task-card')
    .evaluate((card) => {
      const style = window.getComputedStyle(card)
      return {
        paddingTop: style.paddingTop,
        paddingRight: style.paddingRight,
        paddingBottom: style.paddingBottom,
        paddingLeft: style.paddingLeft,
        columnGap: style.columnGap,
      }
    })
  const currentTaskCardTokens = await page.evaluate(() => {
    const rootStyle = window.getComputedStyle(document.documentElement)
    return {
      top: rootStyle
        .getPropertyValue('--visual-v2-business-card-padding-top')
        .trim(),
      right: rootStyle
        .getPropertyValue('--visual-v2-business-card-padding-right')
        .trim(),
      bottom: rootStyle
        .getPropertyValue('--visual-v2-business-card-padding-bottom')
        .trim(),
      left: rootStyle
        .getPropertyValue('--visual-v2-business-card-padding-left')
        .trim(),
    }
  })
  expect(currentTaskCardSpacing).toEqual({
    paddingTop: currentTaskCardTokens.top,
    paddingRight: currentTaskCardTokens.right,
    paddingBottom: currentTaskCardTokens.bottom,
    paddingLeft: currentTaskCardTokens.left,
    columnGap: 'normal',
  })
  await expect(page.locator('.active-task-summary')).toHaveCount(0)
  await expect(
    page.getByRole('region', { name: '设备详情内容' }),
  ).toHaveAttribute('tabindex', '0')
  const layout = await page.evaluate(() => {
    const list = document.querySelector<HTMLElement>(
      '[data-testid="application-list"]',
    )!
    const panel = document.querySelector<HTMLElement>(
      '[data-testid="device-capability-panel"]',
    )!
    const header = panel.querySelector<HTMLElement>(
      '.device-capability-panel__header',
    )!
    const selector = panel.querySelector<HTMLElement>(
      '[data-testid="device-capability-tabs"]',
    )!
    const tabs = Array.from(selector.querySelectorAll<HTMLElement>('.van-tab'))
    const refresh = panel.querySelector<HTMLElement>(
      '[data-testid="device-capability-refresh"]',
    )!
    const rows = Array.from(
      list.querySelectorAll<HTMLElement>('[data-testid="application-row"]'),
    )
    const listBox = list.getBoundingClientRect()
    const headerBox = header.getBoundingClientRect()
    const selectorBox = selector.getBoundingClientRect()
    const titleBox = panel
      .querySelector<HTMLElement>('.device-capability-panel__title')!
      .getBoundingClientRect()
    const rowAnatomy = rows.slice(0, 6).map((row) => {
      const icon = row.querySelector<HTMLElement>(
        '.device-capability-panel__icon-slot',
      )!
      const main = row.querySelector<HTMLElement>(
        '.device-capability-panel__main-content',
      )!
      const name = row.querySelector<HTMLElement>(
        '.device-capability-panel__name',
      )!
      const actions = row.querySelector<HTMLElement>(
        '.device-capability-panel__actions',
      )!
      const buttons = Array.from(
        actions.querySelectorAll<HTMLButtonElement>('button'),
      )
      const rowBox = row.getBoundingClientRect()
      const iconBox = icon.getBoundingClientRect()
      const mainBox = main.getBoundingClientRect()
      const actionsBox = actions.getBoundingClientRect()
      const nameStyle = window.getComputedStyle(name)
      return {
        childOrder: Array.from(row.children).map((child) => child.className),
        iconBeforeMain: iconBox.right <= mainBox.left,
        mainBeforeActions: mainBox.right <= actionsBox.left,
        actionsAtRight: Math.abs(actionsBox.right - rowBox.right) <= 1,
        actionOrder: buttons.map(
          (button) => button.getAttribute('aria-label')?.split('：')[0],
        ),
        iconWidth: iconBox.width,
        iconFontSize: Number.parseFloat(
          window.getComputedStyle(
            icon.querySelector<HTMLElement>('.mobile-icon')!,
          ).fontSize,
        ),
        rowHeight: rowBox.height,
        nameActuallyTruncated: name.scrollWidth > name.clientWidth,
        nameOverflow: nameStyle.overflow,
        nameTextOverflow: nameStyle.textOverflow,
        nameWhiteSpace: nameStyle.whiteSpace,
        actionTargets: buttons.map((button) => {
          const box = button.getBoundingClientRect()
          const visual = button.querySelector<HTMLElement>(
            '.van-button__content > span',
          )!
          return {
            width: box.width,
            height: box.height,
            left: box.left,
            right: box.right,
            visualHeight: visual.getBoundingClientRect().height,
          }
        }),
      }
    })
    return {
      expectedRowHeight: Number.parseFloat(
        window
          .getComputedStyle(document.documentElement)
          .getPropertyValue('--visual-v2-detail-capability-row-height'),
      ),
      fiveRowsFitList:
        rows
          .slice(0, 5)
          .reduce(
            (height, row) => height + row.getBoundingClientRect().height,
            0,
          ) <=
        listBox.height + 1,
      refreshTouchWidth: refresh.getBoundingClientRect().width,
      refreshTouchHeight: refresh.getBoundingClientRect().height,
      refreshVisualSize: (() => {
        const style = window.getComputedStyle(refresh, '::before')
        return {
          width: Number.parseFloat(style.width),
          height: Number.parseFloat(style.height),
        }
      })(),
      refreshText: refresh.textContent?.trim() ?? '',
      refreshAtHeaderRight:
        titleBox.right <= refresh.getBoundingClientRect().left,
      selectorBelowHeader: headerBox.bottom <= selectorBox.top,
      equalTabWidths:
        Math.abs(
          tabs[0]!.getBoundingClientRect().width -
            tabs[1]!.getBoundingClientRect().width,
        ) <= 1,
      rowAnatomy,
      fiveRowsVisible: rows
        .slice(0, 5)
        .every(
          (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
        ),
      sixthRequiresScroll:
        rows[5]!.getBoundingClientRect().top >= listBox.bottom - 1 &&
        rows[5]!.getBoundingClientRect().bottom > listBox.bottom + 1,
      listScrollable: list.scrollHeight > list.clientHeight,
      listScrollbarWidth: window.getComputedStyle(list).scrollbarWidth,
      detailScrollbarWidth: window.getComputedStyle(
        document.querySelector<HTMLElement>('.app-page')!,
      ).scrollbarWidth,
    }
  })
  expect(layout.fiveRowsFitList).toBe(true)
  expect(layout.refreshTouchWidth).toBeGreaterThanOrEqual(44)
  expect(layout.refreshTouchHeight).toBeGreaterThanOrEqual(44)
  expect(layout.refreshVisualSize.height).toBe(34)
  expect(layout.refreshVisualSize.width).toBeGreaterThanOrEqual(44)
  expect(layout.refreshText).toBe('刷新')
  expect(layout.refreshAtHeaderRight).toBe(true)
  expect(layout.selectorBelowHeader).toBe(true)
  expect(layout.equalTabWidths).toBe(true)
  expect(layout.rowAnatomy).toHaveLength(6)
  expect(
    layout.rowAnatomy.every(
      (row) =>
        row.childOrder[0]?.includes('device-capability-panel__icon-slot') &&
        row.childOrder[1]?.includes('device-capability-panel__main-content') &&
        row.childOrder[2]?.includes('device-capability-panel__actions') &&
        row.iconBeforeMain &&
        row.mainBeforeActions &&
        row.actionsAtRight &&
        row.actionOrder.join(',') === '配置,运行' &&
        row.actionTargets.every(
          (action) =>
            action.width >= 44 &&
            action.height >= 44 &&
            action.visualHeight === 34,
        ) &&
        row.actionTargets[0]!.right <= row.actionTargets[1]!.left + 0.5 &&
        row.iconWidth > 0 &&
        row.nameOverflow === 'hidden' &&
        row.nameTextOverflow === 'ellipsis' &&
        row.nameWhiteSpace === 'nowrap',
    ),
  ).toBe(true)
  expect(new Set(layout.rowAnatomy.map((row) => row.iconWidth)).size).toBe(1)
  expect(
    layout.rowAnatomy.every(
      (row) => Math.abs(row.rowHeight - layout.expectedRowHeight) <= 1,
    ),
  ).toBe(true)
  expect(
    layout.rowAnatomy.every(
      (row) => row.iconWidth === 38 && row.iconFontSize === 20,
    ),
  ).toBe(true)
  expect(layout.rowAnatomy[0]?.nameActuallyTruncated).toBe(true)
  expect(layout.fiveRowsVisible).toBe(true)
  expect(layout.sixthRequiresScroll).toBe(true)
  expect(layout.listScrollable).toBe(true)
  expect(layout.listScrollbarWidth).toBe('none')
  expect(layout.detailScrollbarWidth).toBe('none')
  await expect(
    page.getByText('visual-app-orders', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByText('visual-device-operations', { exact: true }),
  ).toBeHidden()
  await expect(page.getByTestId('capability-icon-slot')).toHaveCount(8)
  await expect(page.getByTestId('capability-version')).toHaveCount(0)
  await expect(page.getByText('2026.08', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /配置：拼多多/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /运行：拼多多/ })).toBeVisible()
  const frozenStructure = await page.evaluate(() => {
    const detail = document
      .querySelector<HTMLElement>('[data-testid="device-detail"]')!
      .getBoundingClientRect()
    const detailScroll = document.querySelector<HTMLElement>(
      '[data-testid="device-detail"]',
    )!
    const hero = document
      .querySelector<HTMLElement>('[data-testid="device-detail-hero"]')!
      .getBoundingClientRect()
    const panel = document
      .querySelector<HTMLElement>('[data-testid="device-capability-panel"]')!
      .getBoundingClientRect()
    const taskCard = document
      .querySelector<HTMLElement>(
        '[data-testid="device-current-task"] [data-testid="task-card"]',
      )!
      .getBoundingClientRect()
    const bottom = document
      .querySelector<HTMLElement>('[data-testid="mobile-shell-bottom"]')!
      .getBoundingClientRect()
    return {
      detailStartsInViewport: detail.top >= 0,
      detailScrollable: detailScroll.scrollHeight > detailScroll.clientHeight,
      heroBeforeTask: hero.bottom <= taskCard.top,
      taskBeforePanel: taskCard.bottom <= panel.top,
      taskCardComplete: taskCard.top >= 0 && taskCard.bottom <= bottom.top + 1,
      bottomComplete:
        bottom.top >= 0 && bottom.bottom <= window.innerHeight + 1,
    }
  })
  expect(frozenStructure).toEqual({
    detailStartsInViewport: true,
    detailScrollable: true,
    heroBeforeTask: true,
    taskBeforePanel: true,
    taskCardComplete: true,
    bottomComplete: true,
  })
  await page.screenshot({
    path: testInfo.outputPath('capability-yingdao-390-light.png'),
    clip: { x: 0, y: 0, width: 390, height: 650 },
  })
  await page.screenshot({
    path: testInfo.outputPath('capability-current-task-390-light.png'),
  })

  const applicationList = page.getByTestId('application-list')
  const fixedPanelPositions = await page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>(
      '[data-testid="device-capability-panel"]',
    )!
    return {
      headerTop: panel
        .querySelector<HTMLElement>('.device-capability-panel__header')!
        .getBoundingClientRect().top,
      selectorTop: panel
        .querySelector<HTMLElement>('[data-testid="device-capability-tabs"]')!
        .getBoundingClientRect().top,
    }
  })
  await applicationList.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await expect
    .poll(() => applicationList.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  await expect
    .poll(() =>
      page.evaluate(() => {
        const panel = document.querySelector<HTMLElement>(
          '[data-testid="device-capability-panel"]',
        )!
        return {
          headerTop: panel
            .querySelector<HTMLElement>('.device-capability-panel__header')!
            .getBoundingClientRect().top,
          selectorTop: panel
            .querySelector<HTMLElement>(
              '[data-testid="device-capability-tabs"]',
            )!
            .getBoundingClientRect().top,
        }
      }),
    )
    .toEqual(fixedPanelPositions)
  await page.screenshot({
    path: testInfo.outputPath('capability-yingdao-scrolled-390-light.png'),
    clip: { x: 0, y: 0, width: 390, height: 650 },
  })

  await page.getByRole('tab', { name: 'Skills 5' }).click()
  await expect(page.getByTestId('skill-row')).toHaveCount(5)
  await expect(page.getByText('运行状态检查', { exact: true })).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '配置：订单同步' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '运行：库存同步' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '配置：库存同步' }),
  ).toHaveCount(0)
  await expect(page.getByTestId('capability-icon-slot')).toHaveCount(5)
  await expect(page.getByTestId('capability-version')).toHaveCount(5)
  await expect(page.getByText('v1.3.0', { exact: true })).toBeVisible()
  const fiveSkillRows = await page
    .getByTestId('skill-list')
    .evaluate((list) => {
      const rows = Array.from(
        list.querySelectorAll<HTMLElement>('[data-testid="skill-row"]'),
      )
      const listBox = list.getBoundingClientRect()
      return {
        scrollable: list.scrollHeight > list.clientHeight,
        allRowsVisible: rows.every(
          (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
        ),
        scrollTop: list.scrollTop,
      }
    })
  expect(fiveSkillRows).toEqual({
    scrollable: false,
    allRowsVisible: true,
    scrollTop: 0,
  })
  await page.screenshot({
    path: testInfo.outputPath('capability-skills-390-light.png'),
    clip: { x: 0, y: 0, width: 390, height: 650 },
  })

  await page.getByRole('button', { name: '更多信息' }).click()
  await expect(page.getByTestId('device-more-sheet')).toBeVisible()
  await expect(page.getByTestId('device-more-sheet')).not.toContainText(
    /设备配置|更多设置/,
  )
  await page.getByRole('button', { name: '关闭更多信息' }).click()
  await expect(page.getByTestId('device-more-sheet')).toBeHidden()
  const detailScroll = page.getByRole('region', { name: '设备详情内容' })
  await page.getByRole('tab', { name: '影刀应用 8' }).click()
  await detailScroll.evaluate((element) => {
    element.scrollTop = 0
  })
  await applicationList.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await applicationList.hover()
  await page.mouse.wheel(0, 800)
  await expect
    .poll(() => detailScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)

  await page.getByRole('button', { name: '查看任务：订单同步' }).click()
  await expect(page).toHaveURL(
    /#\/tasks\/visual-task-running\?fromDeviceId=visual-device-operations$/,
  )
  await expect(page.getByTestId('task-detail')).toContainText('订单同步')
  await expect(page.getByTestId('detail-progress-value')).toHaveCount(0)
  await expect(page.getByTestId('task-detail-info-device')).toContainText(
    '运营',
  )
  await expect(page.getByTestId('runtime-events')).toContainText(
    '正在处理 HuanYu 店铺',
  )
  await page.screenshot({
    path: testInfo.outputPath('visual-task-detail-390-light.png'),
  })
  await page.getByRole('button', { name: '返回' }).click()
  await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
  await expect(page.getByTestId('device-current-task-link')).toBeVisible()

  expect(observation.apiRequests).toEqual([])
  expect(observation.consoleErrors).toEqual([])
})

for (const fixture of [
  { width: 360, theme: 'light', file: 'capability-360-light.png' },
  { width: 390, theme: 'dark', file: 'capability-390-dark.png' },
] as const) {
  test(`CapabilityPanel ${fixture.width}px ${fixture.theme} 保持五行与三段行结构`, async ({
    page,
  }, testInfo) => {
    const observation = observePage(page)
    await page.setViewportSize({ width: fixture.width, height: 844 })
    await setTheme(page, fixture.theme)
    await page.goto('/#/devices/visual-device-operations')

    const panel = page.getByTestId('device-capability-panel')
    const list = page.getByTestId('application-list')
    await expect(panel).toBeVisible()
    await expect(page.getByTestId('application-row')).toHaveCount(8)
    const geometry = await list.evaluate((element) => {
      const listBox = element.getBoundingClientRect()
      const rows = Array.from(
        element.querySelectorAll<HTMLElement>(
          '[data-testid="application-row"]',
        ),
      )
      return {
        fiveRowsVisible: rows
          .slice(0, 5)
          .every(
            (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
          ),
        sixthRequiresScroll:
          rows[5]!.getBoundingClientRect().top >= listBox.bottom - 1,
        rowsKeepSlots: rows.slice(0, 5).every((row) => {
          const icon = row
            .querySelector<HTMLElement>('.device-capability-panel__icon-slot')!
            .getBoundingClientRect()
          const main = row
            .querySelector<HTMLElement>(
              '.device-capability-panel__main-content',
            )!
            .getBoundingClientRect()
          const actions = row
            .querySelector<HTMLElement>('.device-capability-panel__actions')!
            .getBoundingClientRect()
          const rowBox = row.getBoundingClientRect()
          return (
            icon.right <= main.left &&
            main.right <= actions.left &&
            actions.right <= rowBox.right + 1
          )
        }),
      }
    })
    expect(geometry).toEqual({
      fiveRowsVisible: true,
      sixthRequiresScroll: true,
      rowsKeepSlots: true,
    })
    await expect(page.getByTestId('capability-icon-slot')).toHaveCount(8)
    await expect(
      page.getByText('visual-app-orders', { exact: true }),
    ).toHaveCount(0)
    await expectNoHorizontalOverflow(page)
    const selectorLayout = await readCapabilityLayout(page)
    expect(selectorLayout).toMatchObject({
      headerBeforeSelector: true,
      selectorBeforeRows: true,
      headerOutsideRows: true,
      selectorOutsideRows: true,
      tabsContained: true,
      activeSurfaceContained: true,
      selectorHasNoInternalOverflow: true,
      fiveRowsVisible: true,
      sixthRequiresScroll: true,
    })
    expect(selectorLayout.touchHeights.every((height) => height >= 44)).toBe(
      true,
    )
    await page.screenshot({
      path: testInfo.outputPath(fixture.file),
      clip: { x: 0, y: 0, width: fixture.width, height: 650 },
    })
    if (fixture.width === 360 && fixture.theme === 'light') {
      await page.screenshot({
        path: testInfo.outputPath('capability-current-task-360-light.png'),
      })
    }

    expect(observation.apiRequests).toEqual([])
    expect(observation.consoleErrors).toEqual([])
  })
}
