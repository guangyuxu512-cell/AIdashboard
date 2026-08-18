import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('validates the Shop Center V3 list, selection, platform switch and detail drawer', async ({
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
  await expect(page.getByRole('heading', { name: '店铺中心' })).toHaveCount(0)
  await expect(
    page.getByText('统一管理平台店铺、会话状态与执行配置'),
  ).toHaveCount(0)
  await expect(
    page.getByRole('navigation', { name: '店铺平台切换' }),
  ).toBeVisible()
  await expect(page.getByAltText('全部平台图标')).toBeVisible()
  await expect(page.getByAltText('抖店平台图标').first()).toBeVisible()
  await expect(page.getByAltText('拼多多平台图标').first()).toBeVisible()
  await expect(page.getByAltText('淘宝平台图标')).toBeVisible()
  await expect(page.getByAltText('视频号平台图标')).toBeVisible()

  const filterBar = page.getByRole('region', { name: '筛选条件' })
  await expect(filterBar).toBeVisible()
  await expect(page.getByPlaceholder('搜索店铺名称')).toBeVisible()
  await expect(filterBar.getByText('店铺状态', { exact: true })).toHaveCount(0)
  await expect(filterBar.getByText('负责人', { exact: true })).toHaveCount(0)
  await expect(filterBar.getByText('关键词', { exact: true })).toHaveCount(0)
  await expect(
    filterBar.getByRole('button', { name: '新增店铺' }),
  ).toBeVisible()
  await expect(page.getByText('店铺列表', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/数据来自 FastAPI/)).toHaveCount(0)
  await expect(page.getByText(/Frontend Fixture/)).toHaveCount(0)
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '开启' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '分组' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '状态' })).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: '今日订单' })).toHaveCount(
    0,
  )
  await expect(page.getByText('今日 GMV')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(page.getByText('未分组').first()).toBeVisible()
  await expect(page.getByText('深圳-工作站-03 +2')).toBeVisible()
  await expect(page.getByRole('switch').first()).toBeDisabled()
  await expect(page.getByText('批量分配分组')).toBeVisible()
  await expect(page.getByText('批量开启')).toBeVisible()
  await expect(page.getByText('批量关闭')).toBeVisible()
  await expect(page.getByText('批量删除')).toBeVisible()
  await expect(page.getByRole('button', { name: '删除' }).first()).toBeDisabled()

  const rowCheckboxes = page.getByRole('checkbox')
  await expect(rowCheckboxes.first()).toBeVisible()
  await rowCheckboxes.nth(1).click()
  await expect(page.getByText('已选择 1 家店铺')).toBeVisible()
  await expect(page.locator('.app-table__row--selected')).toHaveCount(1)
  await rowCheckboxes.first().click()
  await expect(page.getByText('已选择 10 家店铺')).toBeVisible()
  await expect(page.locator('.app-table__row--selected')).toHaveCount(10)

  const compactOrder = await page.evaluate(() => {
    const top = (selector: string) =>
      document.querySelector(selector)?.getBoundingClientRect().top ?? -1
    return {
      platform: top('.shop-platform-switch'),
      filter: top('.filter-bar'),
      table: top('.n-data-table'),
    }
  })
  expect(compactOrder.platform).toBeLessThan(compactOrder.filter)
  expect(compactOrder.filter).toBeLessThan(compactOrder.table)

  await page.getByRole('button', { name: '抖店', exact: true }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toHaveCount(0)

  await page.getByRole('button', { name: '拼多多', exact: true }).click()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()
  await expect(page.getByText('星河服饰旗舰店')).toHaveCount(0)

  await page.getByRole('button', { name: '全部平台', exact: true }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toBeVisible()

  await page.getByRole('button', { name: '淘宝', exact: true }).click()
  await expect(page.getByText('没有符合当前条件的店铺')).toBeVisible()
  await page.getByRole('button', { name: '全部平台', exact: true }).click()

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
  await expect(page.getByText('自动化策略与控制能力尚未接入')).toBeVisible()
  await expect(page.getByText('业务数据同步能力尚未接入')).toBeVisible()
  await expect(page.getByText('店铺操作历史尚未接入')).toBeVisible()
  await expect(page.getByText('自动化总开关待接入')).toBeVisible()
  await expect(page.getByText('未分组').last()).toBeVisible()

  const openContentWidth = await page
    .locator('.app-shell__content')
    .evaluate((element) => element.getBoundingClientRect().width)
  expect(openContentWidth).toBe(closedContentWidth)

  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByText('账号与连接')).toHaveCount(0)

  await page.getByRole('button', { name: '查看' }).nth(2).click()
  await expect(page.getByText('云朵母婴专营店').last()).toBeVisible()
  await expect(page.getByText('shop-fixture-003').first()).toBeVisible()
  await expect(page.getByText('上海-直播机-02、杭州-运营机-01')).toBeVisible()
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

test('keeps the Shop V3 list viewport stable for full, single-row and empty states', async ({
  page,
}) => {
  await page.goto('/#/shops')
  const viewport = page.locator('.data-table--stable')
  await expect(viewport).toBeVisible()
  const fullHeight = await viewport.evaluate((element) =>
    Math.round(element.getBoundingClientRect().height),
  )

  await page.getByPlaceholder('搜索店铺名称').fill('星河')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  const singleHeight = await viewport.evaluate((element) =>
    Math.round(element.getBoundingClientRect().height),
  )

  await page.getByRole('button', { name: '淘宝', exact: true }).click()
  await expect(page.getByText('没有符合当前条件的店铺')).toBeVisible()
  const emptyHeight = await viewport.evaluate((element) =>
    Math.round(element.getBoundingClientRect().height),
  )

  expect(singleHeight).toBe(fullHeight)
  expect(emptyHeight).toBe(fullHeight)
})

test('opens the existing create form from the V3 page', async ({ page }) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true }).last()).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toBeVisible()
  await expect(page.getByText('可选负责人', { exact: true })).toBeVisible()
})

test('renders compact Shop and Device pages in light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()

  await page.getByText('设备中心', { exact: true }).click()
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()
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
