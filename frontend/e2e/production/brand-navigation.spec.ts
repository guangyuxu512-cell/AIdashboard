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

  const navigation = page.getByRole('navigation', { name: '主导航' })
  await expect(navigation).toBeVisible()
  await expect(page.getByText('思余AI中控台', { exact: true })).toBeVisible()
  await expect(page.getByText('运营工作台', { exact: true })).toHaveCount(0)
  await expect(
    navigation.getByText('UI 基础设施', { exact: true }),
  ).toHaveCount(0)
  await expect(page.locator('.app-shell__brand-mark')).toBeVisible()

  for (const theme of ['浅色', '深色']) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.getByText(theme, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute(
      'data-theme',
      theme === '浅色' ? 'light' : 'dark',
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

test('keeps the template visual fixture out of production', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/templates?visualMock=1')

  await expect(page.getByText('暂无模板', { exact: true })).toBeVisible()
  await expect(page.getByText('电商标准套图 A', { exact: true })).toHaveCount(0)
  await expect(page.getByText('竞品复刻 A', { exact: true })).toHaveCount(0)
  await expect(page.getByText('极简白底', { exact: true })).toHaveCount(0)
})
