import { expect, test, type Locator, type Page } from '@playwright/test'

const storageKey = 'control-center.mobile.visual-token-tuner-v1'

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function setRangeValue(locator: Locator, value: number): Promise<void> {
  await locator.evaluate((element, nextValue) => {
    const input = element as HTMLInputElement
    input.value = String(nextValue)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }, value)
}

async function rootValue(page: Page, cssVar: string): Promise<string> {
  return page.evaluate((variable) => {
    return window
      .getComputedStyle(document.documentElement)
      .getPropertyValue(variable)
      .trim()
  }, cssVar)
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

test.describe('Visual Token Tuner V1', () => {
  test.describe.configure({ mode: 'serial' })

  test('在真实 Visual Mock 中实时调节、恢复、复制并在刷新后保留', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.addInitScript((key) => {
      const preparedKey = `${key}.prepared`
      if (!window.sessionStorage.getItem(preparedKey)) {
        window.localStorage.removeItem(key)
        window.sessionStorage.setItem(preparedKey, 'true')
      }
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: (text: string) => {
            ;(
              window as Window & { __visualTokenTunerClipboard?: string }
            ).__visualTokenTunerClipboard = text
            return Promise.resolve()
          },
        },
      })
    }, storageKey)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/devices')

    const entry = page.getByTestId('visual-token-tuner-entry')
    await expect(entry).toBeVisible()

    const entryBox = await entry.boundingBox()
    const profileBox = await page
      .getByTestId('mobile-bottom-navigation-profile')
      .boundingBox()
    expect(entryBox).not.toBeNull()
    expect(profileBox).not.toBeNull()
    expect(entryBox!.y + entryBox!.height).toBeLessThanOrEqual(profileBox!.y)

    const panel = page.getByTestId('visual-token-tuner-panel')
    await expect(panel).toBeHidden()
    await entry.click()

    await expect(panel).toBeVisible()
    await expect(panel).toContainText('已调整 0 项')

    const card = page.getByTestId('device-card').first()
    const baselinePadding = await card.evaluate(
      (element) => window.getComputedStyle(element).paddingTop,
    )
    expect(baselinePadding).toBe('16px')

    await setRangeValue(
      page.getByTestId('visual-token-range-card-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(page, '--layout-card-padding-y'))
      .toBe('20px')
    await expect
      .poll(() =>
        card.evaluate((element) => window.getComputedStyle(element).paddingTop),
      )
      .toBe('20px')

    const numberInput = page.getByTestId('visual-token-number-card-padding-y')
    await numberInput.fill('18')
    await expect(
      page.getByTestId('visual-token-range-card-padding-y'),
    ).toHaveValue('18')
    await expect
      .poll(() => rootValue(page, '--layout-card-padding-y'))
      .toBe('18px')

    await page.getByTestId('visual-token-reset-card-padding-y').click()
    await expect
      .poll(() => rootValue(page, '--layout-card-padding-y'))
      .toBe('16px')
    await expect
      .poll(() =>
        card.evaluate((element) => window.getComputedStyle(element).paddingTop),
      )
      .toBe('16px')

    await page.getByRole('tab', { name: '概览' }).click()
    await setRangeValue(
      page.getByTestId('visual-token-range-summary-height'),
      104,
    )
    await expect
      .poll(() => rootValue(page, '--layout-summary-height'))
      .toBe('104px')
    await expect
      .poll(() =>
        page
          .locator('.mobile-summary-strip')
          .evaluate((element) => window.getComputedStyle(element).height),
      )
      .toBe('104px')

    await page.getByTestId('visual-token-tuner-copy-css').click()
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain('--layout-summary-height: 104px;')
    await page.getByTestId('visual-token-tuner-copy-json').click()
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain('"--layout-summary-height": "104px"')

    await page.getByTestId('visual-token-tuner-close').click()
    await expect(panel).toBeHidden()
    await expectNoHorizontalOverflow(page)

    await page.getByTestId('visual-token-tuner-entry').click()
    await expect(
      page.getByTestId('visual-token-number-summary-height'),
    ).toHaveValue('104')
    await page.getByTestId('visual-token-tuner-close').click()

    await page.getByTestId('visual-token-tuner-entry').click()
    await page.getByRole('tab', { name: '卡片' }).click()
    await setRangeValue(
      page.getByTestId('visual-token-range-card-leading-slot'),
      60,
    )
    await page.getByTestId('visual-token-tuner-close').click()
    await page.reload()

    await expect
      .poll(() => rootValue(page, '--layout-card-leading-icon-slot-width'))
      .toBe('60px')
    await expect
      .poll(() =>
        page
          .getByTestId('device-card-leading')
          .first()
          .evaluate((element) => window.getComputedStyle(element).width),
      )
      .toBe('60px')

    await page.getByTestId('visual-token-tuner-entry').click()
    await expect(
      page.getByTestId('visual-token-number-card-leading-slot'),
    ).toHaveValue('60')
    await page.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(page, '--layout-card-leading-icon-slot-width'))
      .toBe('52px')
    await expect
      .poll(() => rootValue(page, '--layout-summary-height'))
      .toBe('96px')

    expect(consoleErrors).toEqual([])
  })

  test('在深色模式以 Token 样式呈现并保持窄屏底部面板可用', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.addInitScript((key) => {
      window.localStorage.removeItem(key)
      window.localStorage.setItem('control-center.mobile.theme-mode', 'dark')
    }, storageKey)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/devices')

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await page.getByTestId('visual-token-tuner-entry').click()
    await expect(page.getByTestId('visual-token-tuner-panel')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    expect(consoleErrors).toEqual([])
  })

  test('在设备详情中实时调节运行摘要与能力密度，且保持五行滚动边界', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.addInitScript(
      (key) => window.localStorage.removeItem(key),
      storageKey,
    )
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/devices/visual-device-operations')
    await page.getByTestId('visual-token-tuner-entry').click()

    await page.getByRole('tab', { name: '运行摘要' }).click()
    await setRangeValue(
      page.getByTestId('visual-token-range-runtime-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(page, '--layout-runtime-summary-padding-y'))
      .toBe('20px')
    await expect
      .poll(() =>
        page.getByTestId('device-summary-device').evaluate((element) => {
          return window.getComputedStyle(element).paddingTop
        }),
      )
      .toBe('20px')

    await page.getByRole('tab', { name: '能力' }).click()
    await setRangeValue(
      page.getByTestId('visual-token-range-capability-panel-height'),
      374,
    )
    await setRangeValue(
      page.getByTestId('visual-token-range-capability-row-height'),
      52,
    )
    await expect
      .poll(() => rootValue(page, '--layout-capability-panel-height'))
      .toBe('374px')
    await expect
      .poll(() => rootValue(page, '--layout-capability-row-min-height'))
      .toBe('52px')

    const rowsLayout = await page
      .getByTestId('application-list')
      .evaluate((list) => {
        const listBox = list.getBoundingClientRect()
        const rows = Array.from(
          list.querySelectorAll<HTMLElement>('[data-testid="application-row"]'),
        )
        return {
          fiveRowsVisible: rows
            .slice(0, 5)
            .every(
              (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
            ),
          sixthRequiresScroll:
            rows[5]!.getBoundingClientRect().bottom > listBox.bottom + 1,
        }
      })
    expect(rowsLayout).toEqual({
      fiveRowsVisible: true,
      sixthRequiresScroll: true,
    })

    await page.getByTestId('visual-token-tuner-close').click()
    await expectNoHorizontalOverflow(page)
    expect(consoleErrors).toEqual([])
  })
})
