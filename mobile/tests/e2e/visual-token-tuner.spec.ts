import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test'

import { installAuthenticatedMobileSession } from './auth-api-fixture'

const storageKey = 'control-center.mobile.visual-token-tuner-v1'
const appearanceStorageKey = 'control-center.mobile.visual-token-tuner-v3'

test.beforeEach(async ({ page }) => {
  await installAuthenticatedMobileSession(page)
})

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

async function setColorPickerValue(
  locator: Locator,
  value: string,
): Promise<void> {
  await locator.evaluate((element, nextValue) => {
    const input = element as HTMLInputElement
    input.value = nextValue
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

test.describe('Visual Token Tuner V2 / V3', () => {
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
    expect(baselinePadding).toBe('15px')

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
      .toBe('15px')

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
      .toBe('90px')

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
      .toBe('102px')

    await tuner.getByRole('button', { name: '恢复全部调参' }).click()
    await expect(tuner.getByTestId('visual-token-tuner-panel')).toContainText(
      '尺寸已调整 0 项 · 颜色已调整 0 项 · 外观已调整 0 项',
    )
    await expect
      .poll(() =>
        preview.evaluate((key) => window.localStorage.getItem(key), storageKey),
      )
      .toBeNull()
    await expect
      .poll(() => rootValue(preview, '--layout-card-leading-icon-slot-width'))
      .toBe('72px')
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

  test('旧版密度 Token 不穿透已迁移的 Visual V2 设备详情', async ({
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

    const visualV2Baseline = await preview.evaluate(() => {
      const hero = document.querySelector<HTMLElement>(
        '[data-testid="device-detail-hero"]',
      )!
      const row = document.querySelector<HTMLElement>(
        '[data-testid="application-row"]',
      )!
      return {
        heroPaddingTop: window.getComputedStyle(hero).paddingTop,
        capabilityRowHeight: row.getBoundingClientRect().height,
      }
    })

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
        preview.getByTestId('device-detail-hero').evaluate((element) => {
          return window.getComputedStyle(element).paddingTop
        }),
      )
      .toBe(visualV2Baseline.heroPaddingTop)

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
          firstRowHeight: rows[0]!.getBoundingClientRect().height,
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
      firstRowHeight: visualV2Baseline.capabilityRowHeight,
      fiveRowsVisible: true,
      sixthRequiresScroll: true,
    })

    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-capability-panel-height'))
      .toBe('372px')
    await expect
      .poll(() => rootValue(preview, '--layout-runtime-summary-padding-y'))
      .toBe('9px')
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
      .toBe('7px')

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

  test('V2 按主题隔离颜色覆盖，恢复颜色不影响尺寸覆盖', async ({
    page: preview,
    context,
  }) => {
    await prepareClipboard(context)
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices')
    await preview.evaluate((key) => {
      window.localStorage.removeItem(key)
      window.localStorage.setItem('control-center.mobile.theme-mode', 'light')
    }, storageKey)
    await preview.reload()

    const tuner = await openExternalTuner(preview, context)
    const tunerErrors = collectConsoleErrors(tuner)

    await setRangeValue(
      tuner.getByTestId('visual-token-range-card-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')

    await tuner.getByTestId('visual-token-tuner-mode-color').click()
    await tuner.getByTestId('visual-token-tuner-theme-light').click()
    const lightAppBackground = tuner.getByTestId(
      'visual-token-color-hex-light-bg-app',
    )
    await lightAppBackground.fill('#e8edf2')
    await lightAppBackground.press('Tab')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#e8edf2')

    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#101820')

    await tuner.getByTestId('visual-token-tuner-theme-dark').click()
    const darkAppBackground = tuner.getByTestId(
      'visual-token-color-hex-dark-bg-app',
    )
    await darkAppBackground.fill('#0f151d')
    await darkAppBackground.press('Tab')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#0f151d')

    await tuner.getByTestId('visual-token-tuner-copy-color-css').click()
    await expect
      .poll(() =>
        tuner.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain(":root[data-theme='light'] {")
    await tuner.getByTestId('visual-token-tuner-copy-color-json').click()
    await expect
      .poll(() =>
        tuner.evaluate(
          () =>
            (window as Window & { __visualTokenTunerClipboard?: string })
              .__visualTokenTunerClipboard ?? '',
        ),
      )
      .toContain('"dark"')

    await tuner.getByTestId('visual-token-tuner-reset-color-theme').click()
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#101820')
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')

    await tuner.getByTestId('visual-token-tuner-theme-light').click()
    await tuner.getByTestId('visual-token-tuner-reset-all-colors').click()
    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#f4f6f8')
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')

    await tuner.getByTestId('visual-token-tuner-mode-dimension').click()
    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('16px')
    await expectNoHorizontalOverflow(preview)
    await expectNoHorizontalOverflow(tuner)
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })

  test('全局颜色调参保留独立 Device / Task Visual V2，并继续映射未迁移页面', async ({
    page: preview,
    context,
  }) => {
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices')
    await preview.evaluate((key) => {
      window.localStorage.removeItem(key)
      window.localStorage.setItem('control-center.mobile.theme-mode', 'light')
    }, storageKey)
    await preview.reload()

    const deviceCard = preview.getByTestId('device-card').first()
    await expect(deviceCard).toBeVisible()
    const deviceVisualBaseline = await deviceCard.evaluate((element) => ({
      background: window.getComputedStyle(element).backgroundColor,
      title: window.getComputedStyle(
        element.querySelector<HTMLElement>('[data-testid="device-card-name"]')!,
      ).color,
      meta: window.getComputedStyle(
        element.querySelector<HTMLElement>('[data-testid="device-card-meta"]')!,
      ).color,
    }))
    await preview.goto('/#/tasks')
    const taskCard = preview.getByTestId('task-card').first()
    await expect(taskCard).toBeVisible()
    const taskVisualBaseline = await taskCard.evaluate((element) => ({
      background: window.getComputedStyle(element).backgroundColor,
      title: window.getComputedStyle(
        element.querySelector<HTMLElement>('[data-testid="task-card-name"]')!,
      ).color,
    }))
    await preview.goto('/#/devices')
    await expect(deviceCard).toBeVisible()
    const tuner = await openExternalTuner(preview, context)
    const tunerErrors = collectConsoleErrors(tuner)
    await tuner.getByTestId('visual-token-tuner-mode-color').click()
    await tuner.getByTestId('visual-token-tuner-theme-light').click()

    const lightAppBackground = tuner.getByTestId(
      'visual-token-color-hex-light-bg-app',
    )
    await setColorPickerValue(
      tuner.getByTestId('visual-token-color-picker-light-bg-app'),
      '#e8edf2',
    )
    await expect(lightAppBackground).toHaveValue('#e8edf2')
    await expect
      .poll(() =>
        preview.locator('body').evaluate((element) => {
          return window.getComputedStyle(element).backgroundColor
        }),
      )
      .toBe('rgb(232, 237, 242)')

    const lightCardSurface = tuner.getByTestId(
      'visual-token-color-hex-light-bg-surface-raised',
    )
    await lightCardSurface.fill('#f0f4f7')
    await lightCardSurface.press('Tab')
    await expect
      .poll(() =>
        deviceCard.evaluate(
          (element) => window.getComputedStyle(element).backgroundColor,
        ),
      )
      .toBe(deviceVisualBaseline.background)

    await preview.goto('/#/tasks')
    await expect(taskCard).toBeVisible()
    await expect
      .poll(() =>
        taskCard.evaluate(
          (element) => window.getComputedStyle(element).backgroundColor,
        ),
      )
      .toBe(taskVisualBaseline.background)

    await preview.goto('/#/devices')
    await expect(deviceCard).toBeVisible()
    await tuner.getByRole('tab', { name: '文字' }).click()
    const primaryText = tuner.getByTestId(
      'visual-token-color-hex-light-text-primary',
    )
    await primaryText.fill('#203040')
    await primaryText.press('Tab')
    await expect
      .poll(() =>
        preview
          .getByTestId('device-card-name')
          .first()
          .evaluate((element) => window.getComputedStyle(element).color),
      )
      .toBe(deviceVisualBaseline.title)

    await preview.goto('/#/tasks')
    await expect
      .poll(() =>
        preview
          .getByTestId('task-card-name')
          .first()
          .evaluate((element) => window.getComputedStyle(element).color),
      )
      .toBe(taskVisualBaseline.title)
    await preview.goto('/#/devices')
    await expect(deviceCard).toBeVisible()

    const mutedText = tuner.getByTestId(
      'visual-token-color-hex-light-text-muted',
    )
    await mutedText.fill('#617a8d')
    await mutedText.press('Tab')
    await expect
      .poll(() =>
        preview
          .getByTestId('device-card-meta')
          .first()
          .evaluate((element) => window.getComputedStyle(element).color),
      )
      .toBe(deviceVisualBaseline.meta)

    await preview.reload()
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#e8edf2')
    await expect
      .poll(() => rootValue(preview, '--bg-surface-raised'))
      .toBe('#f0f4f7')

    // Force a document navigation: a same-document hash goto can race while
    // the external tuner window and parallel visual workers are active.
    await preview.goto(
      '/?visual-fixture=task-success#/tasks/visual-task-success',
    )
    await expect(preview).toHaveURL(/#\/tasks\/visual-task-success$/)
    await expect(preview.getByTestId('task-detail')).toBeVisible({
      timeout: 10_000,
    })
    await tuner.getByRole('tab', { name: '状态' }).click()
    const onlineStatus = tuner.getByTestId(
      'visual-token-color-hex-light-status-success',
    )
    await onlineStatus.fill('#247a56')
    await onlineStatus.press('Tab')
    const successStatus = preview.getByTestId('task-detail-status')
    await expect(successStatus).toBeVisible()
    await expect
      .poll(() =>
        successStatus.evaluate(
          (element) => window.getComputedStyle(element).color,
        ),
      )
      .toBe('rgb(36, 122, 86)')

    await tuner.getByTestId('visual-token-tuner-theme-dark').click()
    await tuner.getByRole('tab', { name: '颜色与表面' }).click()
    const darkAppBackground = tuner.getByTestId(
      'visual-token-color-hex-dark-bg-app',
    )
    await darkAppBackground.fill('#0f151d')
    await darkAppBackground.press('Tab')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#e8edf2')

    await preview.goto('/#/devices')
    await expect(deviceCard).toBeVisible()
    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#0f151d')

    await tuner.getByTestId('visual-token-tuner-theme-light').click()
    await tuner.getByTestId('visual-token-tuner-reset-color-theme').click()
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#0f151d')

    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#f4f6f8')

    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'dark')
    await tuner.getByTestId('visual-token-tuner-theme-dark').click()
    await tuner.getByTestId('visual-token-tuner-reset-color-theme').click()
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#101820')
    await expectNoHorizontalOverflow(preview)
    await expectNoHorizontalOverflow(tuner)
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })

  test('V3 外观覆盖独立保存，实时作用于 Radius、Border 与 Light / Dark Shadow', async ({
    page: preview,
    context,
  }) => {
    test.setTimeout(60_000)
    await prepareClipboard(context)
    const previewErrors = collectConsoleErrors(preview)
    await preview.setViewportSize({ width: 390, height: 844 })
    await preview.goto('/#/devices')
    await preview.evaluate(
      ([dimensionKey, appearanceKey]) => {
        window.localStorage.removeItem(dimensionKey)
        window.localStorage.removeItem(appearanceKey)
        window.localStorage.setItem('control-center.mobile.theme-mode', 'light')
      },
      [storageKey, appearanceStorageKey],
    )
    await preview.reload()

    const card = preview.getByTestId('device-card').first()
    await expect(card).toBeVisible()
    const beforeGeometry = await card.evaluate((element) => {
      const style = window.getComputedStyle(element)
      const box = element.getBoundingClientRect()
      return {
        height: box.height,
        width: box.width,
        padding: [
          style.paddingTop,
          style.paddingRight,
          style.paddingBottom,
          style.paddingLeft,
        ],
      }
    })

    const tuner = await openExternalTuner(preview, context)
    const tunerErrors = collectConsoleErrors(tuner)
    await tuner.getByTestId('visual-token-tuner-mode-appearance').click()
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-radius-card'),
      22,
    )
    await expect.poll(() => rootValue(preview, '--radius-card')).toBe('22px')
    await expect(card).toHaveCSS('border-radius', '17px')
    await expect
      .poll(() =>
        card.evaluate((element) => {
          const style = window.getComputedStyle(element)
          const box = element.getBoundingClientRect()
          return {
            height: box.height,
            width: box.width,
            padding: [
              style.paddingTop,
              style.paddingRight,
              style.paddingBottom,
              style.paddingLeft,
            ],
          }
        }),
      )
      .toEqual(beforeGeometry)

    await preview.goto('/#/tasks')
    const taskCard = preview.getByTestId('task-card').first()
    await expect(taskCard).toBeVisible()
    await expect(taskCard).toHaveCSS('border-radius', '17px')
    const taskCardHeight = await taskCard.evaluate(
      (element) => element.getBoundingClientRect().height,
    )
    const taskCardShadow = await taskCard.evaluate(
      (element) => window.getComputedStyle(element).boxShadow,
    )

    await preview.goto('/#/devices')
    await expect(card).toBeVisible()
    await card.getByRole('button').click()
    await expect(preview).toHaveURL(/#\/devices\/[^/]+$/)
    const detailPage = preview.getByTestId('device-detail')
    const detailHero = preview.getByTestId('device-detail-hero')
    const capabilityPanel = preview.getByTestId('device-capability-panel')
    await expect(detailPage).toBeVisible()
    await expect(detailHero).toBeVisible()
    await expect(capabilityPanel).toBeVisible()
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-radius-panel'),
      20,
    )
    await expect.poll(() => rootValue(preview, '--radius-panel')).toBe('20px')
    await expect(detailHero).toHaveCSS('border-radius', '18px')
    await expect(capabilityPanel).toHaveCSS('border-radius', '18px')

    await preview.goto('/#/devices')
    await expect(card).toBeVisible()
    await expect(preview.locator('.mobile-summary-strip__surface')).toHaveCSS(
      'border-radius',
      '18px',
    )
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-radius-control'),
      14,
    )
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-radius-tag'),
      16,
    )
    await expect.poll(() => rootValue(preview, '--radius-control')).toBe('14px')
    await expect.poll(() => rootValue(preview, '--radius-tag')).toBe('16px')
    await preview.goto('/#/tasks')
    await expect(taskCard).toBeVisible()
    await expect(taskCard).toHaveCSS('border-radius', '17px')
    await expect(preview.locator('.task-list-card-v2__tag').first()).toHaveCSS(
      'border-radius',
      '14px',
    )
    await preview.getByTestId('mobile-header-menu').click()
    const filterSheet = preview.locator('.task-filter-sheet')
    await expect(filterSheet).toBeVisible()
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-radius-overlay'),
      24,
    )
    await expect.poll(() => rootValue(preview, '--radius-overlay')).toBe('24px')
    await expect(filterSheet).toHaveCSS('border-top-left-radius', '24px')
    await preview.locator('.van-overlay').click({ position: { x: 5, y: 5 } })
    await expect(filterSheet).toBeHidden()

    await expect(taskCard).toBeVisible()

    await tuner.getByRole('tab', { name: '边界' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-border-surface-width'),
      0,
    )
    await expect
      .poll(() => rootValue(preview, '--appearance-border-surface-width'))
      .toBe('0px')
    await expect
      .poll(() =>
        taskCard.evaluate((element) => element.getBoundingClientRect().height),
      )
      .toBe(taskCardHeight)

    await tuner.getByRole('tab', { name: '阴影' }).click()
    await setRangeValue(
      tuner.getByTestId('visual-token-appearance-range-light-shadow-card-blur'),
      32,
    )
    await expect
      .poll(() => rootValue(preview, '--shadow-card-blur'))
      .toBe('32px')
    await expect
      .poll(() =>
        taskCard.evaluate(
          (element) => window.getComputedStyle(element).boxShadow,
        ),
      )
      .toBe(taskCardShadow)
    await taskCard.getByRole('button').click()
    await expect(preview).toHaveURL(/#\/tasks\/[^/]+$/)
    const taskDetailCard = preview.getByTestId('task-detail')
    await expect(taskDetailCard).toBeVisible()
    await expect
      .poll(() =>
        taskDetailCard.evaluate(
          (element) => window.getComputedStyle(element).boxShadow,
        ),
      )
      .toBe(taskCardShadow)
    await setRangeValue(
      tuner.getByTestId(
        'visual-token-appearance-range-light-shadow-card-opacity',
      ),
      12,
    )
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('12%')
    await expect
      .poll(() =>
        taskDetailCard.evaluate(
          (element) => window.getComputedStyle(element).boxShadow,
        ),
      )
      .toBe(taskCardShadow)

    await tuner.getByTestId('visual-token-tuner-appearance-theme-dark').click()
    await setRangeValue(
      tuner.getByTestId(
        'visual-token-appearance-range-dark-shadow-card-opacity',
      ),
      30,
    )
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('12%')
    await preview.goto('/#/tasks')
    await expect(taskCard).toBeVisible()
    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('30%')
    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('12%')

    await tuner.getByTestId('visual-token-tuner-mode-dimension').click()
    await setRangeValue(
      tuner.getByTestId('visual-token-range-card-padding-y'),
      20,
    )
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')

    await tuner.getByTestId('visual-token-tuner-mode-color').click()
    await tuner.getByTestId('visual-token-tuner-theme-light').click()
    await setColorPickerValue(
      tuner.getByTestId('visual-token-color-picker-light-bg-app'),
      '#e8edf2',
    )
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#e8edf2')

    await tuner.getByTestId('visual-token-tuner-mode-appearance').click()
    await tuner.getByTestId('visual-token-tuner-appearance-theme-light').click()
    await tuner.getByTestId('visual-token-tuner-reset-appearance-group').click()
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('5%')
    await expect.poll(() => rootValue(preview, '--radius-card')).toBe('22px')

    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect
      .poll(() => rootValue(preview, '--shadow-card-opacity'))
      .toBe('30%')
    await preview.getByTestId('theme-toggle').click()
    await expect(preview.locator('html')).toHaveAttribute('data-theme', 'light')

    await preview.reload()
    await expect.poll(() => rootValue(preview, '--radius-card')).toBe('22px')
    await expect
      .poll(() => rootValue(preview, '--appearance-border-surface-width'))
      .toBe('0px')

    await tuner.getByTestId('visual-token-tuner-reset-stage3b').click()
    await expect.poll(() => rootValue(preview, '--radius-card')).toBe('18px')
    await expect.poll(() => rootValue(preview, '--radius-panel')).toBe('18px')
    await expect.poll(() => rootValue(preview, '--radius-control')).toBe('12px')
    await expect.poll(() => rootValue(preview, '--radius-tag')).toBe('999px')
    await expect
      .poll(() => rootValue(preview, '--appearance-border-surface-width'))
      .toBe('1px')
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('20px')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#e8edf2')

    await tuner.getByTestId('visual-token-tuner-reset-all').click()
    await expect
      .poll(() => rootValue(preview, '--layout-card-padding-y'))
      .toBe('16px')
    await expect.poll(() => rootValue(preview, '--bg-app')).toBe('#f4f6f8')
    await expect.poll(() => rootValue(preview, '--radius-card')).toBe('18px')
    await expectNoHorizontalOverflow(preview)
    await expectNoHorizontalOverflow(tuner)
    expect(previewErrors).toEqual([])
    expect(tunerErrors).toEqual([])
  })
})
