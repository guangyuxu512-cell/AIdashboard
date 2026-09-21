import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('uses the UI-only dashboard fixture for filtering, pagination and refresh feedback', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/operating-dashboard')

  await expect(page).toHaveURL(/#\/operating-dashboard$/)
  await expect(page.getByRole('region', { name: '经营概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /成交趋势/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '店铺' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '商家体验分' })).toBeVisible()

  await page.getByText('近3天', { exact: true }).click()
  await expect(page.getByText('较上期', { exact: true })).toHaveCount(4)
  await expect(
    page.getByRole('heading', { name: /至 .*成交趋势/ }),
  ).toBeVisible()

  const filter = page.getByRole('region', { name: '筛选条件' })
  await filter.locator('.n-base-selection').last().click()
  await page
    .locator('.app-select-menu--viewport-safe')
    .last()
    .getByText('拼多多', { exact: true })
    .click()
  await expect(
    page.getByRole('columnheader', { name: '商家体验分' }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('row').filter({ hasText: '抖店' }),
  ).toHaveCount(0)

  await page.reload()
  const pagination = page.locator('.pagination-bar')
  await pagination.getByText('2', { exact: true }).click()
  await expect(
    page.getByRole('row').filter({ hasText: 'MyCookLab' }),
  ).toBeVisible()

  await page.getByRole('button', { name: '更新数据', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已更新 10 家')
  await page.getByRole('button', { name: '更新数据', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已完成 11 家店铺')
  expect(runtimeErrors).toEqual([])
})

test('keeps the dashboard table and pagination inside the desktop renderer', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/#/operating-dashboard')
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
  await expect(page.locator('.pagination-bar')).toBeVisible()

  for (const theme of ['浅色', '深色']) {
    await page.getByRole('button', { name: '切换主题', exact: true }).click()
    await page.getByText(theme, { exact: true }).click()
    const layout = await page.evaluate(() => ({
      document:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      body: document.body.scrollWidth > document.body.clientWidth,
      tableHasScrollableViewport:
        document.querySelector('.operating-dashboard-table') !== null,
    }))
    expect(layout).toEqual({
      document: false,
      body: false,
      tableHasScrollableViewport: true,
    })
  }
})
