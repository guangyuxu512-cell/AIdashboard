import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('opens the device center and keeps the standard page behavior', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/shops')
  await page.getByText('设备中心', { exact: true }).click()

  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.getByRole('heading', { name: '设备中心' })).toHaveCount(0)
  await expect(
    page.getByText('统一管理执行设备、运行状态与自动化能力'),
  ).toHaveCount(0)
  await expect(page.getByLabel('设备统计')).toHaveCount(0)
  await expect(page.getByText('设备列表', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/数据来自 FastAPI/)).toHaveCount(0)
  await expect(page.getByText(/Frontend Fixture/)).toHaveCount(0)
  const filterBar = page.getByRole('region', { name: '筛选条件' })
  await expect(filterBar).toBeVisible()
  await expect(filterBar.getByText('设备状态', { exact: true })).toHaveCount(0)
  await expect(filterBar.getByText('设备标签', { exact: true })).toHaveCount(0)
  await expect(filterBar.getByText('Worker 版本', { exact: true })).toHaveCount(
    0,
  )
  await expect(filterBar.getByText('执行能力', { exact: true })).toHaveCount(0)
  await expect(filterBar.getByText('关键词', { exact: true })).toHaveCount(0)
  await expect(
    filterBar.getByRole('button', { name: '添加设备' }),
  ).toBeVisible()
  await expect(page.getByText('杭州-运营机-01', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: '最后心跳' }),
  ).toBeVisible()
  await expect(page.getByText('在线', { exact: true }).first()).toBeVisible()

  await page.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('设备详情', { exact: true })).toBeVisible()
  await expect(page.getByText('执行能力', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('CPU 摘要', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '添加设备' }).click()
  await expect(
    page.getByText('创建设备基础记录', { exact: true }).last(),
  ).toBeVisible()
  await expect(
    page.getByText('创建设备记录不代表 Worker 已注册，也不代表设备在线。'),
  ).toBeVisible()

  const layout = await page.evaluate(() => {
    const mainContent = document.querySelector('.app-shell__content')
    return {
      bodyOverflow: getComputedStyle(document.body).overflow,
      mainOverflowY: mainContent
        ? getComputedStyle(mainContent).overflowY
        : null,
      documentHasHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHasHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
    }
  })

  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.mainOverflowY).toBe('auto')
  expect(layout.documentHasHorizontalOverflow).toBe(false)
  expect(layout.bodyHasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])
})

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps the compact Device Center within ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/devices')
    await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
    await expect(page.getByText('杭州-运营机-01', { exact: true })).toBeVisible()

    const overflow = await page.evaluate(() => ({
      document:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      body: document.body.scrollWidth > document.body.clientWidth,
    }))
    expect(overflow).toEqual({ document: false, body: false })
  })
}
