import { expect, test } from '@playwright/test'

test('renders the desktop AppShell and Design System V2 preview', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/')

  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
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
    const topbar = document.querySelector('.app-shell__topbar')?.getBoundingClientRect()
    const host = document.querySelector('#app-overlay-host')?.getBoundingClientRect()
    const wrapper = document.querySelector('.n-modal-body-wrapper')?.getBoundingClientRect()
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
    const host = document.querySelector('#app-overlay-host')?.getBoundingClientRect()
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
      const topbar = document.querySelector('.app-shell__topbar')?.getBoundingClientRect()
      const drawer = document.querySelector('.n-drawer')?.getBoundingClientRect()
      return { topbarBottom: topbar?.bottom, drawerTop: drawer?.top }
    })
    expect(overlay.drawerTop).toBe(overlay.topbarBottom)
    await page.getByRole('button', { name: '关闭' }).click()
  })
}
