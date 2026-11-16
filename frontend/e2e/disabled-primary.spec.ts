import { expect, test, type Locator, type Page } from '@playwright/test'

const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const

async function selectTheme(page: Page, id: string, label: string) {
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id)
}

async function buttonColors(button: Locator) {
  return button.evaluate((element) => {
    const styles = getComputedStyle(element)
    const root = getComputedStyle(document.documentElement)
    const luminance = (color: string) => {
      const values = color
        .match(/[\d.]+/g)!
        .slice(0, 3)
        .map((part) => {
          const value = Number(part) / 255
          return value <= 0.04045
            ? value / 12.92
            : ((value + 0.055) / 1.055) ** 2.4
        })
      return values[0]! * 0.2126 + values[1]! * 0.7152 + values[2]! * 0.0722
    }
    const contrast = (foreground: string) => {
      const a = luminance(foreground)
      const b = luminance(styles.backgroundColor)
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    }
    const icon = element.querySelector('svg')
    return {
      background: styles.backgroundColor,
      text: styles.color,
      border: styles.getPropertyValue('--n-border-disabled').trim(),
      opacity: styles.opacity,
      cursor: styles.cursor,
      contrast: contrast(styles.color),
      iconContrast: icon ? contrast(getComputedStyle(icon).color) : null,
      disabledBackground: root.getPropertyValue('--bg-subtle').trim(),
      disabledText: root.getPropertyValue('--text-tertiary').trim(),
      enabledBackground: root.getPropertyValue('--color-primary').trim(),
    }
  })
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  // Fail closed: even a regression from Visual Mock into Real cannot submit a job.
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (
      url.origin === new URL(test.info().project.use.baseURL!).origin &&
      !url.pathname.startsWith('/api/')
    )
      await route.continue()
    else await route.abort()
  })
})

for (const [id, label] of themes) {
  test(`${id}: disabled generation buttons and icons are readable and stay distinct`, async ({
    page,
  }, testInfo) => {
    const apiAttempts: string[] = []
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/api/'))
        apiAttempts.push(request.method())
    })
    await page.goto('/#/ai-workbench/generate?visualMock=1')
    await selectTheme(page, id, label)
    const instant = page.getByRole('region', { name: '即时生成配置' })
    const generate = instant.getByRole('button', { name: '生成', exact: true })
    await expect(generate).toBeDisabled()
    await expect(generate.locator('svg')).toBeVisible()
    await generate.screenshot({
      path: testInfo.outputPath(`${id}-instant-disabled-button.png`),
      animations: 'disabled',
    })
    await page.screenshot({
      path: testInfo.outputPath(`${id}-instant-disabled.png`),
      animations: 'disabled',
    })
    const disabledInstant = await buttonColors(generate)
    expect.soft(disabledInstant.contrast).toBeGreaterThanOrEqual(4.5)
    expect.soft(disabledInstant.iconContrast).toBeGreaterThanOrEqual(4.5)
    expect(disabledInstant.opacity).toBe('1')
    expect(disabledInstant.cursor).toBe('not-allowed')

    await instant.getByRole('button', { name: '素材库', exact: true }).click()
    const picker = page.getByRole('dialog')
    await picker.getByRole('button', { name: '选择素材 正面.jpg' }).click()
    await picker.getByRole('button', { name: '选择', exact: true }).click()
    await instant.getByLabel('提示词').fill('仅本地 Mock 验证，不发真实请求')
    await expect(generate).toBeEnabled()
    await generate.screenshot({
      path: testInfo.outputPath(`${id}-instant-enabled-button.png`),
      animations: 'disabled',
    })
    const enabled = await buttonColors(generate)
    expect(enabled.background).not.toBe(disabledInstant.background)
    expect(enabled.contrast).toBeGreaterThanOrEqual(4.5)
    await generate.click()
    await expect(page.getByTestId('instant-result-grid')).toBeVisible()

    await page
      .getByRole('navigation', { name: '生成工作方式' })
      .getByRole('button', { name: '批量生成' })
      .click()
    const batch = page.getByRole('region', { name: '批量生成配置' })
    const start = batch.getByRole('button', { name: '开始生成', exact: true })
    await expect(start).toBeDisabled()
    await expect(start.locator('svg')).toBeVisible()
    await start.screenshot({
      path: testInfo.outputPath(`${id}-batch-disabled-button.png`),
      animations: 'disabled',
    })
    await page.screenshot({
      path: testInfo.outputPath(`${id}-batch-disabled.png`),
      animations: 'disabled',
    })
    const disabledBatch = await buttonColors(start)
    expect.soft(disabledBatch.contrast).toBeGreaterThanOrEqual(4.5)
    expect.soft(disabledBatch.iconContrast).toBeGreaterThanOrEqual(4.5)
    expect(disabledBatch.background).toBe(disabledInstant.background)
    expect(disabledBatch.text).toBe(disabledInstant.text)
    await batch.getByRole('button', { name: '执行检查' }).click()
    await expect(start).toBeEnabled()
    await start.screenshot({
      path: testInfo.outputPath(`${id}-batch-enabled-button.png`),
      animations: 'disabled',
    })
    await start.click()
    await expect(page.getByTestId('batch-execution-viewer')).toBeVisible()
    expect(apiAttempts).toEqual([])
    await testInfo.attach('rendered-button-colors', {
      body: JSON.stringify(
        { disabledInstant, enabled, disabledBatch },
        null,
        2,
      ),
      contentType: 'application/json',
    })
  })

  test(`${id}: shared primary hover, focus, loading and other button tones remain usable`, async ({
    page,
  }, testInfo) => {
    await page.goto('/#/foundation')
    await selectTheme(page, id, label)
    const primary = page.getByRole('button', { name: 'Primary', exact: true })
    await expect(primary).toBeEnabled()
    const normal = await buttonColors(primary)
    expect(normal.contrast).toBeGreaterThanOrEqual(4.5)
    await primary.hover()
    await primary.screenshot({
      path: testInfo.outputPath(`${id}-primary-hover.png`),
      animations: 'disabled',
    })
    const hovered = await buttonColors(primary)
    expect(hovered.contrast).toBeGreaterThanOrEqual(4.5)
    expect(hovered.background).not.toBe(normal.background)
    await page.mouse.move(0, 0)
    await primary.focus()
    await expect(primary).toBeFocused()
    // Naive uses the state border for focus, not a required box-shadow.
    await page.keyboard.press('Tab')
    await page.keyboard.press('Shift+Tab')
    await expect(primary).toBeFocused()
    const focusBorder = primary.locator('.n-button__state-border')
    await expect(focusBorder).toHaveCSS('border-top-style', 'solid')
    await expect(focusBorder).toHaveCSS('border-top-width', '1px')
    await expect(focusBorder).toHaveCSS('border-top-color', normal.background)
    expect((await buttonColors(primary)).contrast).toBeGreaterThanOrEqual(4.5)
    await primary.screenshot({
      path: testInfo.outputPath(`${id}-primary-focus.png`),
      animations: 'disabled',
    })
    for (const name of ['Secondary', 'Danger']) {
      const button = page.getByRole('button', { name, exact: true })
      await expect(button).toBeEnabled()
      await button.hover()
      await button.focus()
      await expect(button).toBeFocused()
    }
    await expect(
      page.getByRole('button', { name: 'Disabled', exact: true }),
    ).toBeDisabled()

    // Isolated loading fixture: mount the real shared component and provider.
    // No production page, generating condition or request path is altered.
    await page.evaluate(async () => {
      const vuePath = '/node_modules/.vite/deps/vue.js'
      const naivePath = '/node_modules/.vite/deps/naive-ui.js'
      const buttonPath = '/src/shared/ui/AppButton.vue'
      const overridesPath = '/src/app/providers/naive-theme.ts'
      const { createApp, h } = await import(vuePath)
      const { NConfigProvider, darkTheme } = await import(naivePath)
      const { default: AppButton } = await import(buttonPath)
      const { createNaiveThemeOverrides } = await import(overridesPath)
      const host = document.createElement('div')
      document.querySelector('.control-preview')!.append(host)
      createApp({
        render: () =>
          h(
            NConfigProvider,
            {
              theme:
                document.documentElement.dataset.theme === 'dark'
                  ? darkTheme
                  : null,
              themeOverrides: createNaiveThemeOverrides(),
            },
            {
              default: () =>
                h(
                  AppButton,
                  { tone: 'primary', loading: true },
                  () => 'Loading Primary',
                ),
            },
          ),
      }).mount(host)
    })
    const loading = page.getByRole('button', { name: /Loading Primary/ })
    await expect(loading).toHaveClass(/n-button--loading/)
    await expect(loading.locator('svg')).toBeVisible()
    const loadingColors = await buttonColors(loading)
    expect(loadingColors.contrast).toBeGreaterThanOrEqual(4.5)
    expect(loadingColors.iconContrast).toBeGreaterThanOrEqual(4.5)
    await loading.screenshot({
      path: testInfo.outputPath(`${id}-primary-loading.png`),
      animations: 'disabled',
    })
    await page.screenshot({
      path: testInfo.outputPath(`${id}-shared-states.png`),
      animations: 'disabled',
    })
  })
}
