import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('validates the Shop Center V2 list, platform switch and detail drawer', async ({
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
  await expect(
    page.getByRole('navigation', { name: '店铺平台切换' }),
  ).toBeVisible()
  await expect(page.getByAltText('全部平台图标')).toBeVisible()
  await expect(page.getByAltText('抖店平台图标').first()).toBeVisible()
  await expect(page.getByAltText('拼多多平台图标').first()).toBeVisible()

  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
  await expect(page.getByPlaceholder('搜索店铺名称')).toBeVisible()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '开启' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '今日订单' })).toHaveCount(
    0,
  )
  await expect(page.getByText('今日 GMV')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)

  await page.getByRole('button', { name: '抖店', exact: true }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toHaveCount(0)

  await page.getByRole('button', { name: '拼多多', exact: true }).click()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()
  await expect(page.getByText('星河服饰旗舰店')).toHaveCount(0)

  await page.getByRole('button', { name: '全部平台', exact: true }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()

  await page.getByPlaceholder('搜索店铺名称').fill('星河')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toHaveCount(0)
  await page.getByRole('button', { name: '重置' }).click()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()

  const closedContentWidth = await page
    .locator('.app-shell__content')
    .evaluate((element) => element.getBoundingClientRect().width)

  await page.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('星河服饰旗舰店').last()).toBeVisible()
  await expect(page.getByText('账号与连接')).toBeVisible()
  await expect(page.getByText('账号、Cookie 与连接状态尚未接入')).toBeVisible()
  await expect(page.getByText('自动化配置与控制能力尚未接入')).toBeVisible()
  await expect(page.getByText('业务数据同步能力尚未接入')).toBeVisible()

  const openContentWidth = await page
    .locator('.app-shell__content')
    .evaluate((element) => element.getBoundingClientRect().width)
  expect(openContentWidth).toBe(closedContentWidth)

  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByText('账号与连接')).toHaveCount(0)

  await page.getByRole('button', { name: '查看' }).nth(1).click()
  await expect(page.getByText('海风家居生活馆').last()).toBeVisible()
  await expect(page.getByText('shop-fixture-002').first()).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()

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

test('opens the existing create form from the V2 page', async ({ page }) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true }).last()).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toBeVisible()
  await expect(page.getByText('可选负责人', { exact: true })).toBeVisible()
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps Shop Center and its drawer within ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/shops')
    await expect(page.getByText('星河服饰旗舰店')).toBeVisible()

    const assertNoPageOverflow = async () => {
      const overflow = await page.evaluate(() => ({
        document:
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
        body: document.body.scrollWidth > document.body.clientWidth,
      }))
      expect(overflow).toEqual({ document: false, body: false })
    }

    await assertNoPageOverflow()
    await page.getByRole('button', { name: '查看' }).first().click()
    await expect(page.getByText('账号与连接')).toBeVisible()
    await assertNoPageOverflow()
    await page.getByRole('button', { name: '关闭', exact: true }).click()
  })
}
