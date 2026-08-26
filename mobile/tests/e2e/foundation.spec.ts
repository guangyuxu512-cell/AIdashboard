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
      const pageStyle = styleFor('.app-page')
      return {
        headerTop: headerStyle.paddingTop,
        mainBottom: mainStyle.paddingBottom,
        pageRight: pageStyle.paddingRight,
        pageLeft: pageStyle.paddingLeft,
      }
    })
    expect(safeAreaStyles).toEqual({
      headerTop: safeAreaFixture.top,
      mainBottom: safeAreaFixture.bottom,
      pageRight: safeAreaFixture.right,
      pageLeft: safeAreaFixture.left,
    })

    const openSheetButton = page.getByRole('button', {
      name: '打开底部面板',
    })
    const buttonBox = await openSheetButton.boundingBox()
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44)

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
    await page.getByRole('button', { name: '关闭' }).click()
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

  await page.getByRole('button', { name: '浅色' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.locator('html')).not.toHaveClass(/van-theme-dark/)

  await page.emulateMedia({ colorScheme: 'dark' })
  await page.getByRole('button', { name: '跟随系统' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('html')).toHaveClass(/van-theme-dark/)

  expect(consoleErrors).toEqual([])
})
