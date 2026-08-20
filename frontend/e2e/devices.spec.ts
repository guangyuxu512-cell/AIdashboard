import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('renders the 2.5D device office, opens the correct drawer, and switches views', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/devices')
  await page.getByLabel('切换主题').click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.getByTestId('device-office-stage')).toBeVisible()
  await expect(page.getByText('Light office artwork pending')).toBeVisible()
  await expect(page.getByRole('button', { name: /查看设备/ })).toHaveCount(9)
  await expect(page.getByText('杭州-运营机-01', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '查看设备 杭州-运营机-01' }).click()
  await expect(page.getByText('设备详情', { exact: true })).toBeVisible()
  await expect(page.getByText('device-fixture-001', { exact: true })).toBeVisible()
  await expect(page.getByText('CPU 摘要', { exact: true })).toHaveCount(0)
  await expect(page.getByText('内存摘要', { exact: true })).toHaveCount(0)
  await expect(page.getByText('执行关系', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '列表' }).click()
  await expect(page.getByRole('columnheader', { name: '设备名称' })).toBeVisible()
  await expect(page.getByTestId('device-office-stage')).toHaveCount(0)
  await page.getByRole('button', { name: '办公区' }).click()
  await expect(page.getByTestId('device-office-stage')).toBeVisible()

  await page.getByLabel('切换主题').click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  const officeStage = page.getByTestId('device-office-stage')
  await expect(officeStage).toHaveClass(/device-office-stage--dark/)
  await expect(officeStage).toHaveAttribute('data-stage-mode', 'REFERENCE_PREVIEW')
  await expect(officeStage.getByText('ART ASSETS PENDING')).toBeVisible()
  await expect(officeStage.locator('.workstation-hotspot')).toHaveCount(9)
  await expect(
    officeStage.locator('.mascot-actor[data-asset-status="missing"]'),
  ).toHaveCount(9)
  await expect(
    officeStage.locator('img[src*="dark-office-master.png"]'),
  ).toBeVisible()

  await page
    .getByRole('button', { name: '打开设备标签 上海-直播机-02' })
    .click()
  await expect(page.getByText('device-fixture-002', { exact: true })).toBeVisible()
  await expect(
    page.locator('.n-drawer').getByText('上海-直播机-02', { exact: true }),
  ).toBeVisible()

  const overflow = await page.evaluate(() => ({
    document:
      document.documentElement.scrollWidth > document.documentElement.clientWidth,
    body: document.body.scrollWidth > document.body.clientWidth,
  }))
  expect(overflow).toEqual({ document: false, body: false })
  expect(runtimeErrors).toEqual([])
})

test('uses nine devices per page and preserves empty workstations', async ({ page }) => {
  await page.goto('/#/devices')
  await expect(page.locator('[data-testid^="office-slot-"]')).toHaveCount(9)
  await expect(page.getByRole('button', { name: /查看设备/ })).toHaveCount(9)
  await page
    .locator('.pagination-bar .n-pagination-item')
    .filter({ hasText: '2' })
    .click()
  await expect(page.getByRole('button', { name: /查看设备/ })).toHaveCount(2)
  await expect(page.getByRole('button', { name: /空工位/ })).toHaveCount(7)
})

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps the complete office usable within ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/devices')
    const office = page.getByTestId('device-office-stage')
    await expect(office).toBeVisible()
    await expect(
      page.getByRole('button', { name: '查看设备 杭州-运营机-01' }),
    ).toBeVisible()

    const bounds = await office.boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.width).toBeLessThanOrEqual(viewport.width)
    expect(bounds!.height).toBeGreaterThan(400)
  })
}
