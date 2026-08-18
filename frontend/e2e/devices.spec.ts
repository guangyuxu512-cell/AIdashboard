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
  await expect(page.getByRole('heading', { name: '设备中心' })).toBeVisible()
  await expect(page.getByLabel('设备统计')).toBeVisible()
  await expect(page.getByText('设备总数', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
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
