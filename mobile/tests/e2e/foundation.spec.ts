import { expect, test, type Page } from '@playwright/test'

const viewportWidths = [360, 375, 390, 430] as const
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

async function readVisualMetrics(page: Page) {
  return page.evaluate(() => {
    const parseColor = (value: string): [number, number, number] => {
      const channels = value
        .match(/[\d.]+/g)
        ?.slice(0, 3)
        .map(Number)
      if (!channels || channels.length !== 3) {
        throw new Error(`无法解析颜色：${value}`)
      }
      return channels as [number, number, number]
    }
    const luminance = (value: string) =>
      parseColor(value)
        .map((channel) => channel / 255)
        .map((channel) =>
          channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4,
        )
        .reduce(
          (total, channel, index) =>
            total + channel * [0.2126, 0.7152, 0.0722][index]!,
          0,
        )
    const contrast = (foreground: string, background: string) => {
      const foregroundLuminance = luminance(foreground)
      const backgroundLuminance = luminance(background)
      return (
        (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
        (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
      )
    }
    const style = (selector: string) => {
      const element = document.querySelector<HTMLElement>(selector)
      if (!element) throw new Error(`未找到视觉验证节点：${selector}`)
      return window.getComputedStyle(element)
    }
    const resolveTokenColor = (
      token: string,
      property: 'color' | 'background',
    ) => {
      const probe = document.createElement('span')
      probe.style[property] = `var(${token})`
      document.body.append(probe)
      const computed = window.getComputedStyle(probe)
      const value =
        property === 'color' ? computed.color : computed.backgroundColor
      probe.remove()
      return value
    }
    const statusSelectors = [
      '.foundation-swatch--primary',
      '.foundation-swatch--success',
      '.foundation-swatch--warning',
      '.foundation-swatch--danger',
    ]
    const noticeStates = ['success', 'warning', 'danger'] as const
    const noticeStyles = noticeStates.map((state) => {
      const computed = style(`.mobile-notice-bar--${state}`)
      return {
        color: computed.color,
        background: computed.backgroundColor,
      }
    })

    return {
      surfaces: {
        app: style('html').backgroundColor,
        primary: style('.foundation-surface--primary').backgroundColor,
        secondary: style('.foundation-surface--secondary').backgroundColor,
        raised: style('.foundation-surface--raised').backgroundColor,
      },
      statusContrasts: statusSelectors.map((selector) => {
        const computed = style(selector)
        return contrast(computed.color, computed.backgroundColor)
      }),
      noticeStyles,
      expectedNoticeStyles: noticeStates.map((state) => ({
        color: resolveTokenColor(`--status-${state}`, 'color'),
        background: resolveTokenColor(`--status-${state}-soft`, 'background'),
      })),
      noticeContrasts: noticeStyles.map((notice) =>
        contrast(notice.color, notice.background),
      ),
      tertiaryContrast: contrast(
        style('.foundation-type-scale__meta').color,
        style('.foundation-section').backgroundColor,
      ),
    }
  })
}

for (const width of viewportWidths) {
  test(`基础设施在 ${width}px 视口保持触控和布局基线`, async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/#/__foundation')
    await applySafeAreaFixture(page)

    await expect(
      page.getByRole('heading', { name: '移动端基础设施', level: 1 }),
    ).toBeVisible()
    await expect(page.getByTestId('safe-area-status')).toBeVisible()
    expect(await page.evaluate(() => navigator.maxTouchPoints)).toBeGreaterThan(
      0,
    )

    const safeAreaStyles = await page.evaluate(() => {
      const styleFor = (selector: string) => {
        const element = document.querySelector<HTMLElement>(selector)
        if (!element) throw new Error(`未找到安全区验证节点：${selector}`)
        return window.getComputedStyle(element)
      }

      const headerStyle = styleFor('.mobile-app-shell__header')
      const mainStyle = styleFor('.mobile-app-shell__main')
      const bottomStyle = styleFor('.mobile-app-shell__bottom')
      const pageStyle = styleFor('.app-page')
      return {
        headerTop: headerStyle.paddingTop,
        mainBottom: mainStyle.paddingBottom,
        bottomPadding: bottomStyle.paddingBottom,
        pageRight: pageStyle.paddingRight,
        pageLeft: pageStyle.paddingLeft,
      }
    })
    expect(safeAreaStyles).toEqual({
      headerTop: safeAreaFixture.top,
      mainBottom: '0px',
      bottomPadding: safeAreaFixture.bottom,
      pageRight: safeAreaFixture.right,
      pageLeft: safeAreaFixture.left,
    })
    await expect(page.locator('.van-tabbar-item')).toHaveText([
      '设备',
      '任务',
      '计划',
      '店铺',
      '我的',
    ])

    const openSheetButton = page.getByRole('button', {
      name: '打开底部面板',
    })
    const buttonBox = await openSheetButton.boundingBox()
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44)
    await openSheetButton.focus()
    const focusRing = await openSheetButton.evaluate((element) => {
      const style = window.getComputedStyle(element)
      const probe = document.createElement('span')
      probe.style.color = 'var(--focus-ring-color)'
      document.body.append(probe)
      const expectedColor = window.getComputedStyle(probe).color
      probe.remove()
      return {
        style: style.outlineStyle,
        width: style.outlineWidth,
        color: style.outlineColor,
        expectedColor,
      }
    })
    expect(focusRing).toMatchObject({
      style: 'solid',
      width: '2px',
      color: focusRing.expectedColor,
    })

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    )
    expect(hasHorizontalOverflow).toBe(false)

    await openSheetButton.click()
    await expect(
      page.getByRole('heading', { name: '底部面板', level: 2 }),
    ).toBeVisible()
    const sheetSafeArea = await page
      .locator('.foundation-sheet')
      .evaluate((element) => {
        const style = window.getComputedStyle(element)
        return {
          right: style.paddingRight,
          bottom: style.paddingBottom,
          left: style.paddingLeft,
        }
      })
    expect(sheetSafeArea).toEqual({
      right: safeAreaFixture.right,
      bottom: '43px',
      left: safeAreaFixture.left,
    })
    const closeSheetButton = page.getByRole('button', { name: '关闭' })
    expect(
      (await closeSheetButton.boundingBox())?.height,
    ).toBeGreaterThanOrEqual(44)
    await closeSheetButton.click()
    await expect(
      page.getByRole('heading', { name: '底部面板', level: 2 }),
    ).toBeHidden()

    expect(consoleErrors).toEqual([])
  })
}

test('浅色、深色与跟随系统主题驱动根元素和 Vant', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/__foundation')

  await page.getByRole('button', { name: '深色' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('html')).toHaveClass(/van-theme-dark/)
  const darkMetrics = await readVisualMetrics(page)
  expect(new Set(Object.values(darkMetrics.surfaces)).size).toBe(4)
  expect(Math.min(...darkMetrics.statusContrasts)).toBeGreaterThanOrEqual(4.5)
  expect(darkMetrics.noticeStyles).toEqual(darkMetrics.expectedNoticeStyles)
  expect(Math.min(...darkMetrics.noticeContrasts)).toBeGreaterThanOrEqual(4.5)
  expect(darkMetrics.tertiaryContrast).toBeGreaterThanOrEqual(4.5)

  await page.getByRole('button', { name: '浅色' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.locator('html')).not.toHaveClass(/van-theme-dark/)
  const lightMetrics = await readVisualMetrics(page)
  expect(lightMetrics.surfaces.app).not.toBe(lightMetrics.surfaces.primary)
  expect(lightMetrics.surfaces.primary).not.toBe(
    lightMetrics.surfaces.secondary,
  )
  expect(Math.min(...lightMetrics.statusContrasts)).toBeGreaterThanOrEqual(4.5)
  expect(lightMetrics.noticeStyles).toEqual(lightMetrics.expectedNoticeStyles)
  expect(Math.min(...lightMetrics.noticeContrasts)).toBeGreaterThanOrEqual(4.5)
  expect(lightMetrics.tertiaryContrast).toBeGreaterThanOrEqual(4.5)

  await page.emulateMedia({ colorScheme: 'dark' })
  await page.getByRole('button', { name: '跟随系统' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('html')).toHaveClass(/van-theme-dark/)

  expect(consoleErrors).toEqual([])
})
