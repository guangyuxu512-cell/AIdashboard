import { expect, test } from '@playwright/test'

test('keeps the production brand compact and hides development navigation', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
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
  await expect(page.locator('.app-shell__brand-mark')).toBeVisible()

  for (const theme of ['石墨浅色', '午夜青']) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(theme, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute(
      'data-theme',
      theme === '石墨浅色' ? 'light' : 'dark',
    )
  }

  const layout = await page.evaluate(() => ({
    hasHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    brandAlignment: getComputedStyle(
      document.querySelector('.app-shell__brand') as HTMLElement,
    ).alignItems,
  }))

  expect(layout.hasHorizontalOverflow).toBe(false)
  expect(layout.brandAlignment).toBe('center')
  expect(runtimeErrors).toEqual([])
})

test('keeps every AI visual fixture out of a production-like build', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/templates?visualMock=1')

  await expect(page.getByRole('region', { name: '模板库工具栏' })).toBeVisible()
  await expect(page.getByText('电商标准套图 A', { exact: true })).toHaveCount(0)
  await expect(page.getByText('竞品复刻 A', { exact: true })).toHaveCount(0)
  await expect(page.getByText('极简白底', { exact: true })).toHaveCount(0)

  await page.goto('/#/ai-workbench/generate?visualMock=1')
  await expect(page.getByRole('navigation', { name: 'AI 功能入口' })).toBeVisible()
  await expect(page.getByText('手机支架', { exact: true })).toHaveCount(0)

  await page.goto('/#/ai-workbench/records?visualMock=1')
  await expect(page.getByLabel('生成记录列表')).toBeVisible()
  await expect(page.getByText('张三', { exact: true })).toHaveCount(0)
})
