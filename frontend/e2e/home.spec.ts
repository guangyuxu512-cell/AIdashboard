import { expect, test } from '@playwright/test'

async function ensureAutomationNavigationExpanded(
  page: import('@playwright/test').Page,
): Promise<void> {
  const deviceNavigation = page.getByText('设备中心', { exact: true })
  if (await deviceNavigation.isVisible()) return

  await page.getByText('自动化中心', { exact: true }).click()
  await expect(deviceNavigation).toBeVisible()
}

test('renders the desktop AppShell and Design System V2 preview', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/')

  const navigation = page.getByRole('navigation', {
    name: '主导航',
    exact: true,
  })
  await expect(navigation).toBeVisible()
  await expect(page.getByText('思余AI中控台', { exact: true })).toBeVisible()
  await expect(page.getByText('运营工作台', { exact: true })).toHaveCount(0)
  await expect(
    navigation.getByText('UI 基础设施', { exact: true }),
  ).toHaveCount(0)
  const brandMark = page.locator('.app-shell__brand-mark')
  await expect(brandMark).toBeVisible()
  expect(
    await brandMark.evaluate((element) =>
      element instanceof HTMLImageElement ? element.naturalWidth : 0,
    ),
  ).toBeGreaterThan(0)
  await expect(
    page.getByRole('heading', { name: 'Design System Playground' }),
  ).toBeVisible()
  await expect(
    page.getByText('颜色、排版、间距、尺寸与布局的唯一视觉来源'),
  ).toBeVisible()
  await expect(page.getByPlaceholder('搜索基础设施')).toBeVisible()
  await expect(page.getByRole('button', { name: '切换主题' })).toBeVisible()

  await page.getByRole('button', { name: '打开 Dialog' }).click()
  await expect(page.getByText('Dialog 主题验收', { exact: true })).toBeVisible()
  const dialogLayout = await page.evaluate(() => {
    const topbar = document
      .querySelector('.app-shell__topbar')
      ?.getBoundingClientRect()
    const host = document
      .querySelector('#app-overlay-host')
      ?.getBoundingClientRect()
    const wrapper = document
      .querySelector('.n-modal-body-wrapper')
      ?.getBoundingClientRect()
    return {
      topbarBottom: topbar?.bottom,
      hostTop: host?.top,
      wrapperTop: wrapper?.top,
    }
  })
  expect(dialogLayout.hostTop).toBe(dialogLayout.topbarBottom)
  expect(dialogLayout.wrapperTop).toBe(dialogLayout.hostTop)
  await page.getByRole('button', { name: '取消' }).click()
  await page.getByRole('button', { name: '打开 Drawer' }).click()
  await expect(page.getByText('Drawer 主题验收', { exact: true })).toBeVisible()
  const drawerLayout = await page.evaluate(() => {
    const host = document
      .querySelector('#app-overlay-host')
      ?.getBoundingClientRect()
    const drawer = document.querySelector('.n-drawer')?.getBoundingClientRect()
    return {
      hostTop: host?.top,
      drawerTop: drawer?.top,
      drawerBottom: drawer?.bottom,
      viewportHeight: window.innerHeight,
    }
  })
  expect(drawerLayout.drawerTop).toBe(drawerLayout.hostTop)
  expect(drawerLayout.drawerBottom).toBe(drawerLayout.viewportHeight)
  await page.getByRole('button', { name: '关闭' }).click()

  const layout = await page.evaluate(() => ({
    bodyOverflow: getComputedStyle(document.body).overflow,
    hasHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  }))

  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.hasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])
})

test('switches and persists light, dark and system themes', async ({
  page,
}) => {
  await page.goto('/')

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: '打开 Dialog' }).click()
  await expect(page.getByText('Dialog 主题验收', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  await page.getByRole('button', { name: '打开 Drawer' }).click()
  await expect(page.getByText('Drawer 主题验收', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await page.emulateMedia({ colorScheme: 'dark' })
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('跟随系统', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.emulateMedia({ colorScheme: 'light' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByTitle('当前主题：跟随系统')).toBeVisible()
})

test('keeps every primary navigation row aligned when groups toggle', async ({
  page,
}) => {
  const viewports = [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1366, height: 768 },
  ]

  const measure = async () =>
    page.evaluate(() => {
      const labels = Array.from(
        document.querySelectorAll<HTMLElement>('.app-shell__nav-label'),
      )
      const rows = labels.map((label) => {
        const content = label.closest<HTMLElement>('.n-menu-item-content')
        const icon = content?.querySelector<HTMLElement>(
          ':scope > .n-menu-item-content__icon',
        )
        const arrow = content?.querySelector<HTMLElement>(
          ':scope > .n-menu-item-content__arrow',
        )
        const labelRect = label.getBoundingClientRect()
        const contentRect = content?.getBoundingClientRect()
        const iconRect = icon?.getBoundingClientRect()
        const arrowRect = arrow?.getBoundingClientRect()
        return {
          text: label.textContent?.trim(),
          labelX: labelRect.x,
          iconCenterX: iconRect ? iconRect.x + iconRect.width / 2 : null,
          rowHeight: contentRect?.height,
          arrowLeft: arrowRect?.left ?? null,
          labelRight: labelRect.right,
        }
      })
      return { rows }
    })

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.goto('/#/tasks')

    for (const theme of ['浅色', '深色']) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page.getByText(theme, { exact: true }).click()
      await ensureAutomationNavigationExpanded(page)

      const expanded = await measure()
      expect(expanded.rows.length).toBeGreaterThanOrEqual(3)
      expect(new Set(expanded.rows.map((row) => row.labelX)).size).toBe(1)
      expect(new Set(expanded.rows.map((row) => row.iconCenterX)).size).toBe(1)
      expect(new Set(expanded.rows.map((row) => row.rowHeight)).size).toBe(1)
      const [automationBox, deviceBox] = await Promise.all([
        page.getByText('自动化中心', { exact: true }).boundingBox(),
        page.getByText('设备中心', { exact: true }).boundingBox(),
      ])
      expect(deviceBox?.x).toBeGreaterThan(automationBox?.x ?? 0)
      const groupRow = expanded.rows.find((row) => row.text === '自动化中心')
      expect(groupRow?.arrowLeft).not.toBeNull()
      expect(groupRow?.arrowLeft ?? 0).toBeGreaterThanOrEqual(
        (groupRow?.labelRight ?? 0) - 4,
      )

      await page.getByText('自动化中心', { exact: true }).click()
      const collapsed = await measure()
      expect(new Set(collapsed.rows.map((row) => row.labelX)).size).toBe(1)
      expect(new Set(collapsed.rows.map((row) => row.iconCenterX)).size).toBe(1)
      await page.getByText('自动化中心', { exact: true }).click()
    }
  }
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`fills the renderer at ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/')

    const layout = await page.evaluate(() => {
      const bounds = (selector: string) => {
        const element = document.querySelector(selector)
        if (!element) return null
        const rect = element.getBoundingClientRect()
        return { height: rect.height, bottom: rect.bottom, width: rect.width }
      }
      const content = document.querySelector('.app-shell__content')
      return {
        viewportHeight: window.innerHeight,
        viewportWidth: window.innerWidth,
        app: bounds('#app'),
        shell: bounds('.app-shell'),
        sidebar: bounds('.app-shell__sidebar'),
        workspace: bounds('.app-shell__workspace'),
        content: bounds('.app-shell__content'),
        contentOverflowY: content ? getComputedStyle(content).overflowY : null,
        documentHasHorizontalOverflow:
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      }
    })

    expect(layout.app?.height).toBe(viewport.height)
    expect(layout.shell?.height).toBe(viewport.height)
    expect(layout.sidebar?.bottom).toBe(viewport.height)
    expect(layout.workspace?.bottom).toBe(viewport.height)
    expect(layout.content?.bottom).toBe(viewport.height)
    expect(layout.contentOverflowY).toBe('auto')
    expect(layout.documentHasHorizontalOverflow).toBe(false)

    await page.getByRole('button', { name: '打开 Drawer' }).click()
    const overlay = await page.evaluate(() => {
      const topbar = document
        .querySelector('.app-shell__topbar')
        ?.getBoundingClientRect()
      const drawer = document
        .querySelector('.n-drawer')
        ?.getBoundingClientRect()
      return { topbarBottom: topbar?.bottom, drawerTop: drawer?.top }
    })
    expect(overlay.drawerTop).toBe(overlay.topbarBottom)
    await page.getByRole('button', { name: '关闭' }).click()
  })
}
