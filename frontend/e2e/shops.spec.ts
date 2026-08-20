import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('validates the Shop Center V4 list, selection, platform registry and detail drawer', async ({
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
  await expect(page.getByRole('columnheader', { name: '分组' })).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: '状态' })).toHaveCount(0)
  await expect(
    page.getByRole('columnheader', { name: '今日订单' }),
  ).toHaveCount(0)
  await expect(page.getByText('今日 GMV')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(page.getByText('未分组')).toHaveCount(0)
  await expect(page.getByText('深圳-工作站-03 +2')).toBeVisible()
  await expect(page.getByRole('switch').first()).toBeDisabled()
  await expect(page.getByText('批量分配分组')).toHaveCount(0)
  await expect(page.getByText('批量开启')).toBeVisible()
  await expect(page.getByText('批量关闭')).toBeVisible()
  await expect(page.getByText('批量删除')).toBeVisible()
  await expect(
    page.getByRole('button', { name: '删除' }).first(),
  ).toBeDisabled()

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
  const closedSectionHeight = await page
    .locator('.shop-list-section')
    .evaluate((element) => Math.round(element.getBoundingClientRect().height))

  await page.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('星河服饰旗舰店').last()).toBeVisible()
  const drawerSafeArea = await page.evaluate(() => {
    const topbar = document.querySelector('.app-shell__topbar')?.getBoundingClientRect()
    const drawer = document.querySelector('.n-drawer')?.getBoundingClientRect()
    return { topbarBottom: topbar?.bottom, drawerTop: drawer?.top }
  })
  expect(drawerSafeArea.drawerTop).toBe(drawerSafeArea.topbarBottom)
  const drawerShopId = await page
    .locator('.shop-detail__id')
    .first()
    .innerText()
  await expect(page.locator('.shop-detail-header')).toContainText('抖店')
  await expect(page.locator('.shop-detail-header')).not.toContainText(
    drawerShopId,
  )
  await expect(page.getByRole('heading', { name: '账号与连接' })).toBeVisible()
  await expect(
    page
      .getByRole('row', { name: /Cookie \/ Session/ })
      .getByText('未配置', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '配置账号与连接' }),
  ).toBeEnabled()
  await expect(page.getByText('Cookie / Session')).toBeVisible()
  await expect(
    page
      .getByRole('row', { name: /Cookie \/ Session/ })
      .getByText('未配置', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '打开浏览器登录' }),
  ).toBeDisabled()
  await expect(page.getByRole('button', { name: '验证连接' })).toBeDisabled()
  await page.getByRole('button', { name: '配置账号与连接' }).click()
  await page
    .getByPlaceholder('手机号、邮箱、用户名或账号 ID')
    .fill('13812348888')
  await page.getByPlaceholder('请输入登录密码').fill('fixture-password')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(
    page.getByRole('row', { name: /登录账号/ }).getByText('138****8888'),
  ).toBeVisible()
  await expect(
    page.getByRole('row', { name: /登录密码/ }).getByText('已配置'),
  ).toBeVisible()
  await expect(page.getByText('fixture-password')).toHaveCount(0)
  await expect(page.getByText('基本信息')).toBeVisible()
  await expect(page.getByText('执行设备', { exact: true }).last()).toBeVisible()
  await expect(page.getByRole('heading', { name: '操作记录' })).toBeVisible()
  await expect(page.getByText('暂无操作记录')).toBeVisible()
  await expect(
    page.getByRole('button', { name: /(?:查看|复制|导出).*Cookie/ }),
  ).toHaveCount(0)
  await expect(page.getByText('自动化策略')).toHaveCount(0)
  await expect(page.getByText('数据同步')).toHaveCount(0)
  await expect(page.getByText('未分组')).toHaveCount(0)

  const openContentWidth = await page
    .locator('.app-shell__content')
    .evaluate((element) => element.getBoundingClientRect().width)
  expect(openContentWidth).toBe(closedContentWidth)

  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByRole('heading', { name: '账号与连接' })).toHaveCount(0)
  await expect(page.locator('.shop-list-section')).toHaveCSS('flex-grow', '1')
  const restoredSectionHeight = await page
    .locator('.shop-list-section')
    .evaluate((element) => Math.round(element.getBoundingClientRect().height))
  expect(restoredSectionHeight).toBe(closedSectionHeight)

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

test('fills the remaining workspace and pins pagination for multi-row, one-row and empty states', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/shops')
  const section = page.locator('.shop-list-section')
  const pagination = section.locator('.pagination-bar')
  await expect(section).toBeVisible()

  const measureLayout = async () => {
    const sectionBox = await section.boundingBox()
    const paginationBox = await pagination.boundingBox()
    const workspaceBox = await page.locator('.app-shell__content').boundingBox()
    if (!sectionBox || !paginationBox || !workspaceBox) {
      throw new Error('列表布局不可测量')
    }
    return {
      sectionHeight: Math.round(sectionBox.height),
      paginationY: Math.round(paginationBox.y),
      paginationBottomGap: Math.round(
        sectionBox.y +
          sectionBox.height -
          (paginationBox.y + paginationBox.height),
      ),
      workspaceBottomGap: Math.round(
        workspaceBox.y +
          workspaceBox.height -
          (sectionBox.y + sectionBox.height),
      ),
    }
  }

  const multiRowLayout = await measureLayout()
  const multiRowHeight = await section
    .getByRole('row')
    .nth(1)
    .evaluate((element) => Math.round(element.getBoundingClientRect().height))

  await page.getByPlaceholder('搜索店铺名称').fill('星河')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  const oneRowLayout = await measureLayout()
  const oneRowHeight = await section
    .getByRole('row')
    .nth(1)
    .evaluate((element) => Math.round(element.getBoundingClientRect().height))

  await page.getByRole('button', { name: '淘宝', exact: true }).click()
  await expect(page.getByText('没有符合当前条件的店铺')).toBeVisible()
  const emptyLayout = await measureLayout()

  expect(oneRowLayout).toEqual(multiRowLayout)
  expect(emptyLayout).toEqual(multiRowLayout)
  expect(oneRowHeight).toBe(multiRowHeight)
  expect(multiRowLayout.paginationBottomGap).toBeGreaterThan(0)
  expect(multiRowLayout.paginationBottomGap).toBeLessThanOrEqual(20)
  expect(multiRowLayout.workspaceBottomGap).toBeGreaterThanOrEqual(12)
  expect(multiRowLayout.workspaceBottomGap).toBeLessThanOrEqual(20)
})

test('drives the Shop Onboarding shell from shared platform and device data', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true })).toBeVisible()
  await expect(page.getByText('选择平台', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('账号与密码', { exact: true })).toBeVisible()
  await expect(page.getByText('登录设备', { exact: true })).toBeVisible()
  await expect(page.getByText('准备连接', { exact: true })).toBeVisible()
  await expect(page.getByText('登录成功后自动读取')).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toHaveCount(0)

  await page.locator('.n-drawer .n-base-selection').click()
  const options = page.locator('.n-base-select-option')
  await expect(options.filter({ hasText: '抖店' })).toBeVisible()
  await expect(options.filter({ hasText: '拼多多' })).toBeVisible()
  await expect(options.filter({ hasText: '淘宝' })).not.toHaveClass(/--disabled/)
  await expect(options.filter({ hasText: '视频号' })).not.toHaveClass(
    /--disabled/,
  )
  await options.filter({ hasText: '淘宝' }).click()
  await expect(page.getByText('该平台已注册，但登录执行能力尚未接入。')).toBeVisible()
  await expect(page.getByAltText('淘宝平台图标').last()).toBeVisible()
  await page.getByRole('button', { name: '下一步' }).click()

  await page
    .getByPlaceholder('手机号、邮箱、用户名或账号 ID')
    .fill('13812348888')
  await page.getByPlaceholder('请输入登录密码').fill('onboarding-password')
  await page.getByRole('button', { name: '下一步' }).click()

  await page.locator('.n-drawer .n-base-selection').click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '深圳-工作站-03' })
    .click()
  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('138****8888')).toBeVisible()
  await expect(page.getByText('深圳-工作站-03', { exact: true }).last()).toBeVisible()
  await expect(page.getByRole('button', { name: '打开浏览器并登录' })).toBeDisabled()
  await expect(page.getByText('待 Worker Browser Session Manager 接入')).toBeVisible()
  await expect(page.getByText('onboarding-password')).toHaveCount(0)

  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '新增店铺' }).click()
  await page.getByRole('button', { name: '开发：Legacy Onboarding' }).click()
  await expect(page.getByText('新增店铺（Legacy Onboarding）')).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toBeVisible()
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
  await expect(page.getByTestId('device-office-scene')).toBeVisible()
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
    await expect(page.getByText('基本信息')).toBeVisible()
    const safeArea = await page.evaluate(() => {
      const topbar = document.querySelector('.app-shell__topbar')?.getBoundingClientRect()
      const drawer = document.querySelector('.n-drawer')?.getBoundingClientRect()
      return { topbarBottom: topbar?.bottom, drawerTop: drawer?.top }
    })
    expect(safeArea.drawerTop).toBe(safeArea.topbarBottom)
    await assertNoPageOverflow()
    await page.getByRole('button', { name: '关闭', exact: true }).click()
  })
}
