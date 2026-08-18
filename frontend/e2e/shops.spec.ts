import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('opens the shop center flows without runtime or horizontal page errors', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/')
  await page.getByText('店铺中心', { exact: true }).click()

  await expect(page).toHaveURL(/#\/shops$/)
  await expect(page.getByRole('heading', { name: '店铺中心' })).toBeVisible()
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: '自动化状态' }),
  ).toBeVisible()

  await page.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('店铺详情', { exact: true })).toBeVisible()
  await expect(page.getByText('执行与配置状态')).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true }).last()).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toBeVisible()
  await expect(page.getByText('可选负责人', { exact: true })).toBeVisible()

  const layout = await page.evaluate(() => ({
    documentHasHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    bodyHasHorizontalOverflow:
      document.body.scrollWidth > document.body.clientWidth,
  }))

  expect(layout.documentHasHorizontalOverflow).toBe(false)
  expect(layout.bodyHasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])
})
