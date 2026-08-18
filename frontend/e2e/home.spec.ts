import { expect, test } from '@playwright/test'

test('renders the desktop AppShell and design system preview', async ({ page }) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/')

  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Frontend Design System' })).toBeVisible()
  await expect(page.getByText('阶段 0B · UI 基础设施')).toBeVisible()
  await expect(page.getByText('颜色、排版、间距、尺寸与布局的唯一视觉来源')).toBeVisible()
  await expect(page.getByPlaceholder('搜索基础设施')).toBeVisible()

  const layout = await page.evaluate(() => ({
    bodyOverflow: getComputedStyle(document.body).overflow,
    hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }))

  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.hasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])
})
