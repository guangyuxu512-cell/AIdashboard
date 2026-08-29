import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test'

const storageKey = 'control-center.mobile.visual-token-tuner-v1'

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function prepareClipboard(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
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
  })
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

async function openExternalTuner(
  preview: Page,
  context: BrowserContext,
): Promise<Page> {
  const externalPage = context.waitForEvent('page')
  await preview.getByTestId('visual-token-tuner-entry').click()
  const tuner = await externalPage
  await tuner.waitForLoadState('domcontentloaded')
  await expect(tuner).toHaveURL(/#\/__visual-tuner$/)
  await expect(tuner.getByTestId('visual-token-tuner-panel')).toBeVisible()
  return tuner
}

test.describe('Visual Token Tuner V1', () => {
  test.describe.configure({ mode: 'serial' })

  test('在独立窗口实时调节真实预览、恢复、复制并在刷新后保留', async ({
    page: preview,
    context,
  }) => {
    await prepareClipboard(context)
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices')
    await preview.evaluate(
      (key) => window.localStorage.removeItem(key),
      storageKey,
    )
    await preview.reload()

    const entry = preview.getByTestId('visual-token-tuner-entry')
    await expect(entry).toBeVisible()
    await expect(preview.getByTestId('visual-token-tuner-panel')).toHaveCount(0)

    const entryBox = await entry.boundingBox()
    const profileBox = await preview
      .getByTestId('mobile-bottom-navigation-profile')
      .boundingBox()
    expect(entryBox).not.toBeNull()
    expect(profileBox).not.toBeNull()
    expect(entryBox!.y + entryBox!.height).toBeLessThanOrEqual(profileBox!.y)

    const card = preview.getByTestId('device-card').first()
    await expect(card).toBeVisible()
    await expectNoHorizontalOverflow(preview)
    const baselinePadding = await card.evaluate(
      (element) => window.getComputedStyle(element).paddingTop,
    )
    expect(baselinePadding).toBe('16px')

    const tuner = await openExternalTuner(preview, context)
    const tunerErrors = collectConsoleErrors(tuner)
    await expect(
      tuner.getByTestId('mobile-bottom-navigation-devices'),
    ).toHaveCount(0)
    await expect(tuner.getByTestId('mobile-global-header')).toHaveCount(0)
    await expect(tuner.getByTestId('visual-token-tuner-panel')).toContainText(
      '已调整 0 项',
    )

    await setRangeValue(
      tuner.getByTestId('visual-token-range-card-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')
    await expect
      .poll(() =>
        card.evaluate((element) => window.getComputedStyle(element).paddingTop),
      )
      .toBe('20px')

    const numberInput = tuner.getByTestId('visual-token-number-card-padding-y')
    await numberInput.fill('18')
    await expect(
      tuner.getByTestId('visual-token-range-card-padding-y'),
    ).toHaveValue('18')
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('18px')

    await tuner.getByTestId('visual-token-reset-card-padding-y').click()
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('16px')

    await tuner.getByRole('tab', { name: '概览' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-summary-height'),
      104,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-summary-height'))
      .toBe('104px')
    await expect
      .poll(() =>
        preview
          .locator('.mobile-summary-strip')
          .evaluate((element) => window.getComputedStyle(element).height),
      )
      .toBe('104px')

    await tuner.getByTestId('visual-token-tuner-copy-css').click()
    await expect
      .poll(() =>
        tuner.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain('--layout-summary-height: 104px;')
    await tuner.getByTestId('visual-token-tuner-copy-json').click()
    await expect
      .poll(() =>
        tuner.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain('"--layout-summary-height": "104px"')

    await tuner.getByRole('tab', { name: '卡片' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-card-leading-slot'),
      60,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-icon-slot-width'))
      .toBe('60px')
    await preview.reload()
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-icon-slot-width'))
      .toBe('60px')
    await expect
      .poll(() =>
        preview
          .getByTestId('device-card-leading')
          .first()
          .evaluate((element) => window.getComputedStyle(element).width),
      )
      .toBe('60px')

    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-icon-slot-width'))
      .toBe('52px')
    await expect
      .poll(() => rootValue(preview, '--layout-summary-height'))
      .toBe('96px')
    await expectNoHorizontalOverflow(preview)
    await expectNoHorizontalOverflow(tuner)
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })

  test('独立调参页在深色模式使用 Token，且不渲染产品 Shell', async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page)
    await page.addInitScript((key) => {
      window.localStorage.removeItem(key)
      window.localStorage.setItem('control-center.mobile.theme-mode', 'dark')
    }, storageKey)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/__visual-tuner')

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect(page.getByTestId('visual-token-tuner-panel')).toBeVisible()
    await expect(
      page.getByTestId('mobile-bottom-navigation-devices'),
    ).toHaveCount(0)
    await expect(page.getByTestId('mobile-global-header')).toHaveCount(0)
    await expectNoHorizontalOverflow(page)
    expect(consoleErrors).toEqual([])
  })

  test('独立调参页可同步设备详情的运行摘要与能力密度', async ({
    page: preview,
    context,
  }) => {
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices/visual-device-operations')
    await preview.evaluate(
      (key) => window.localStorage.removeItem(key),
      storageKey,
    )
    await preview.reload()

    const tuner = await context.newPage()
    const tunerErrors = collectConsoleErrors(tuner)
    await tuner.goto('/#/__visual-tuner')
    await expect(tuner.getByTestId('visual-token-tuner-panel')).toBeVisible()

    await tuner.getByRole('tab', { name: '运行摘要' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-runtime-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-runtime-summary-padding-y'))
      .toBe('20px')
    await expect
      .poll(() =>
        preview.getByTestId('device-summary-device').evaluate((element) => {
          return window.getComputedStyle(element).paddingTop
        }),
      )
      .toBe('20px')

    await tuner.getByRole('tab', { name: '能力' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-capability-panel-height'),
      384,
    )
    await setRangeValue(
      tuner.getByTestId('visual-token-range-capability-row-height'),
      52,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-capability-panel-height'))
      .toBe('384px')
    await expect
      .poll(() => rootValue(preview, '--layout-capability-row-min-height'))
      .toBe('52px')

    const rowsLayout = await preview
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

    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-capability-panel-height'))
      .toBe('372px')
    await expectNoHorizontalOverflow(preview)
    await expectNoHorizontalOverflow(tuner)
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })

  test('语义间距控件只影响所属区域，不穿透到其他组件或 Vant', async ({
    page: preview,
    context,
  }) => {
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices')
    await preview.evaluate((key) => {
      window.localStorage.removeItem(key)
      document.documentElement.style.removeProperty('--space-1')
      document.documentElement.style.removeProperty('--space-2')
    }, storageKey)
    await preview.reload()

    const tuner = await openExternalTuner(preview, context)
    const tunerErrors = collectConsoleErrors(tuner)

    await tuner.getByRole('tab', { name: '卡片' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-card-leading-content-gap'),
      12,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-content-gap'))
      .toBe('12px')
    await expect
      .poll(() => rootValue(preview, '--layout-toolbar-group-gap'))
      .toBe('16px')
    await expect.poll(() => rootValue(preview, '--space-1')).toBe('4px')
    await expect.poll(() => rootValue(preview, '--space-2')).toBe('8px')

    await tuner.getByRole('tab', { name: '概览' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-summary-metric-gap'),
      6,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-summary-metric-gap'))
      .toBe('6px')
    await expect
      .poll(() => rootValue(preview, '--layout-toolbar-inner-gap'))
      .toBe('2px')
    await expect
      .poll(() =>
        preview
          .locator('.mobile-summary-strip__metric')
          .first()
          .evaluate((element) => window.getComputedStyle(element).rowGap),
      )
      .toBe('6px')

    await preview.goto('/#/devices/visual-device-operations')
    await tuner.getByRole('tab', { name: '运行摘要' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-runtime-leading-content-gap'),
      12,
    )
    await expect
      .poll(() =>
        rootValue(preview, '--layout-runtime-summary-leading-content-gap'),
      )
      .toBe('12px')
    await expect
      .poll(() => rootValue(preview, '--layout-toolbar-inner-gap'))
      .toBe('2px')

    await tuner.getByRole('tab', { name: '能力' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-capability-row-gap'),
      12,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-capability-row-gap'))
      .toBe('12px')
    await expect.poll(() => rootValue(preview, '--van-padding-xs')).toBe('16px')
    await expectNoHorizontalOverflow(preview)

    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-content-gap'))
      .toBe('16px')
    await expect
      .poll(() => rootValue(preview, '--layout-summary-metric-gap'))
      .toBe('2px')
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })
})
