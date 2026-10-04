import { expect, test, type Page } from '@playwright/test'

const themes = [
  {
    id: 'graphite',
    label: '石墨浅色',
    surface: 'rgb(255, 255, 255)',
    primary: 'rgb(37, 99, 235)',
  },
  {
    id: 'forest',
    label: '森林绿',
    surface: 'rgb(255, 255, 255)',
    primary: 'rgb(47, 111, 69)',
  },
  {
    id: 'coral',
    label: '珊瑚红',
    surface: 'rgb(255, 255, 255)',
    primary: 'rgb(213, 46, 59)',
  },
  {
    id: 'midnight',
    label: '午夜青',
    surface: 'rgb(19, 43, 69)',
    primary: 'rgb(18, 160, 143)',
  },
]

async function selectTheme(page: Page, theme: (typeof themes)[number]) {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: '切换主题' }).click()
  await page
    .locator('.n-dropdown')
    .getByText(theme.label, { exact: true })
    .click()
  await expect(page.locator('html')).toHaveAttribute(
    'data-theme-preset',
    theme.id,
  )
  await expect(page.locator('html')).toHaveAttribute(
    'data-theme',
    theme.id === 'midnight' ? 'dark' : 'light',
  )
}

test('four rendered themes preserve filters, layouts and preferences and synchronize controls and overlays', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/shops')
  await expect(
    page.getByRole('columnheader', { name: '店铺名称' }),
  ).toBeVisible()
  let originalBounds: unknown
  for (const theme of themes) {
    await selectTheme(page, theme)
    const bounds = await page.locator('.app-shell__sidebar').boundingBox()
    if (!originalBounds) originalBounds = bounds
    expect(bounds).toEqual(originalBounds)
    await page.screenshot({
      path: testInfo.outputPath(`${theme.id}-shops.png`),
      animations: 'disabled',
    })
  }
  await page.goto('/#/foundation')
  const input = page.getByPlaceholder('搜索基础设施')
  await input.fill('保留输入与页面')
  const initialBody = await page.locator('.page-container').elementHandle()
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/api/'))
      writes.push(request.method())
  })
  for (const theme of themes) {
    await selectTheme(page, theme)
    await expect(input).toHaveValue('保留输入与页面')
    expect(await initialBody?.evaluate((element) => element.isConnected)).toBe(
      true,
    )
    const primary = page.getByRole('button', { name: 'Primary', exact: true })
    await expect(primary).toHaveCSS('background-color', theme.primary)
    const expectedText = await page.evaluate(() => {
      const hex = getComputedStyle(document.documentElement)
        .getPropertyValue('--text-primary')
        .trim()
        .slice(1)
      return `rgb(${hex
        .match(/.{2}/g)!
        .map((part) => parseInt(part, 16))
        .join(', ')})`
    })
    await expect(page.locator('.n-result-header__title')).toHaveCSS(
      'color',
      expectedText,
    )
    await expect(
      input.locator(
        'xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," n-input ")][1]',
      ),
    ).toHaveCSS('background-color', theme.surface)
    await page.screenshot({
      animations: 'disabled',
      path: testInfo.outputPath(`${theme.id}-controls.png`),
    })
    await page.getByRole('button', { name: '打开 Dialog' }).click()
    await expect(page.locator('.n-card').last()).toHaveCSS(
      'background-color',
      theme.surface,
    )
    await page.screenshot({
      path: testInfo.outputPath(`${theme.id}-dialog.png`),
      animations: 'disabled',
    })
    await page.getByRole('button', { name: '取消' }).click()
    await page.locator('.n-base-selection').first().click()
    await expect(page.locator('.n-base-select-menu').last()).toHaveCSS(
      'background-color',
      theme.surface,
    )
    await page.keyboard.press('Escape')
    await page.getByRole('heading', { name: '控件与页面模式' }).click()
    await page.locator('.n-date-picker input').click()
    await expect(page.locator('.n-date-panel')).toBeVisible()
    await expect(page.locator('.n-date-panel')).toHaveCSS(
      'background-color',
      theme.surface,
    )
    await page.screenshot({
      path: testInfo.outputPath(`${theme.id}-date-panel.png`),
      animations: 'disabled',
    })
    await page.keyboard.press('Escape')
  }
  expect(writes).toEqual([])
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute(
    'data-theme-preset',
    'midnight',
  )
})

test('semantic text and primary buttons meet contrast targets in all four palettes', async ({
  page,
}) => {
  await page.goto('/#/foundation')
  for (const theme of themes) {
    await selectTheme(page, theme)
    const checks = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement)
      const color = (name: string) => styles.getPropertyValue(name).trim()
      const luminance = (value: string) => {
        const rgb = value
          .replace('#', '')
          .match(/.{2}/g)!
          .map((part) => parseInt(part, 16) / 255)
        const linear = rgb.map((part) =>
          part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4,
        )
        return linear[0]! * 0.2126 + linear[1]! * 0.7152 + linear[2]! * 0.0722
      }
      const contrast = (foreground: string, background: string) => {
        const a = luminance(color(foreground))
        const b = luminance(color(background))
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
      }
      const pairs = [
        ...[
          '--text-primary',
          '--text-secondary',
          '--text-tertiary',
          '--text-link',
        ].flatMap((text) =>
          ['--bg-app', '--bg-surface', '--bg-subtle', '--bg-surface-hover'].map(
            (surface) => [text, surface],
          ),
        ),
        ...[
          '--color-primary',
          '--color-primary-hover',
          '--color-primary-pressed',
        ].map((background) => ['--text-on-primary', background]),
        ['--sidebar-text', '--bg-sidebar'],
        ['--sidebar-text-active', '--sidebar-item-hover'],
        ['--sidebar-text-active', '--sidebar-item-active'],
        ...['info', 'success', 'warning', 'danger'].map((status) => [
          `--status-${status}`,
          `--status-${status}-soft`,
        ]),
      ]
      return pairs.map(([foreground, background]) => ({
        foreground,
        background,
        ratio: contrast(foreground!, background!),
      }))
    })
    for (const check of checks)
      expect(
        check.ratio,
        `${theme.id} ${check.foreground}/${check.background}`,
      ).toBeGreaterThanOrEqual(4.5)
    await expect(
      page.getByRole('button', { name: 'Disabled', exact: true }),
    ).toBeDisabled()
    const primary = page.getByRole('button', { name: 'Primary', exact: true })
    for (const state of ['normal', 'hover', 'pressed']) {
      if (state !== 'normal') await primary.hover()
      if (state === 'pressed') await page.mouse.down()
      const actualContrast = await primary.evaluate((button) => {
        const styles = getComputedStyle(button)
        const luminance = (color: string) => {
          const channels = color
            .match(/[\d.]+/g)!
            .slice(0, 3)
            .map((part) => Number(part) / 255)
          const values = channels.map((part) =>
            part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4,
          )
          return values[0]! * 0.2126 + values[1]! * 0.7152 + values[2]! * 0.0722
        }
        const a = luminance(styles.color)
        const b = luminance(styles.backgroundColor)
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
      })
      expect(
        actualContrast,
        `${theme.id} rendered button ${state}`,
      ).toBeGreaterThanOrEqual(4.5)
      if (state === 'pressed') await page.mouse.up()
    }
  }
})

test('an existing business form stays open with its unsaved draft across all four themes', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '查看', exact: true }).first().click()
  await page
    .locator('.shop-detail-header')
    .getByRole('button', { name: '编辑', exact: true })
    .click()
  const note = page.getByPlaceholder('请输入备注（选填）')
  await note.fill('主题切换验收：仅草稿，不保存')
  const originalForm = await page.locator('.shop-form__grid').elementHandle()
  for (const theme of themes) {
    await selectTheme(page, theme)
    await expect(note).toHaveValue('主题切换验收：仅草稿，不保存')
    // Sticky table cells must stay behind the modal after removing blur.
    expect(
      await page.locator('.shop-form__grid').evaluate((form) => {
        const rect = form.getBoundingClientRect()
        return form.contains(
          document.elementFromPoint(rect.left + rect.width / 2, rect.top + 12),
        )
      }),
    ).toBe(true)
    expect(await originalForm?.evaluate((element) => element.isConnected)).toBe(
      true,
    )
    await expect(page.locator('.app-dialog').last()).toHaveCSS(
      'background-color',
      theme.surface,
    )
    await page.screenshot({
      animations: 'disabled',
      path: testInfo.outputPath(`${theme.id}-shop-form.png`),
    })
  }
  await page.getByRole('button', { name: '取消', exact: true }).click()
})

test('existing PC pages use the four palettes without horizontal overflow or runtime errors', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const path of [
    '/shops',
    '/assets',
    '/ai-workbench/generate',
    '/operating-dashboard',
    '/parameter-presets',
    '/devices',
    '/tasks',
    '/settings/users',
  ]) {
    await page.goto(`/#${path}`)
    await expect(page.locator('.app-shell')).toBeVisible()
    for (const theme of themes) {
      await selectTheme(page, theme)
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true)
      await expect(page.locator('.app-shell__topbar')).toHaveCSS(
        'backdrop-filter',
        'none',
      )
    }
  }
  expect(errors).toEqual([])
})
