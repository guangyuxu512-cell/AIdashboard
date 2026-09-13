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
  const platformNavigation = page.getByRole('navigation', {
    name: '店铺平台切换',
  })
  await expect(platformNavigation).toBeVisible()
  await expect(platformNavigation.getByRole('button')).toHaveCount(5)
  await expect(
    platformNavigation.getByRole('button', { name: '全部平台' }),
  ).toHaveAttribute('aria-pressed', 'true')
  for (const platform of ['全部平台', '抖店', '拼多多', '淘宝', '视频号']) {
    await expect(
      platformNavigation.getByRole('button', { name: platform }),
    ).toBeEnabled()
  }
  await expect(page.getByAltText('全部平台图标')).toBeVisible()
  await expect(page.getByAltText('抖店平台图标').first()).toBeVisible()
  await expect(page.getByAltText('拼多多平台图标').first()).toBeVisible()
  await expect(page.getByAltText('淘宝平台图标')).toBeVisible()
  await expect(page.getByAltText('视频号平台图标')).toBeVisible()

  const platformCellAlignment = await page
    .locator('.n-data-table-tbody .platform-display')
    .evaluateAll((displays) =>
      displays.map((display) => {
        const iconSlot = display.querySelector<HTMLElement>(
          '.platform-display__icon-slot',
        )
        const icon = iconSlot?.querySelector<HTMLElement>('.platform-icon')
        const label = display.querySelector<HTMLElement>(
          '.platform-display__label',
        )
        const displayRect = display.getBoundingClientRect()
        const iconSlotRect = iconSlot?.getBoundingClientRect()
        const iconRect = icon?.getBoundingClientRect()
        const labelRect = label?.getBoundingClientRect()
        return {
          iconSlotWidth: Math.round(iconSlotRect?.width ?? 0),
          iconCenterOffset: Math.round(
            (iconRect?.left ?? 0) + (iconRect?.width ?? 0) / 2 -
              ((iconSlotRect?.left ?? 0) + (iconSlotRect?.width ?? 0) / 2),
          ),
          labelOffset: Math.round((labelRect?.left ?? 0) - displayRect.left),
          gap: Math.round(
            (labelRect?.left ?? 0) -
              ((iconSlotRect?.left ?? 0) + (iconSlotRect?.width ?? 0)),
          ),
          labelTextAlign: label ? getComputedStyle(label).textAlign : null,
        }
      }),
    )
  expect(platformCellAlignment.length).toBeGreaterThan(1)
  expect(
    new Set(platformCellAlignment.map((item) => item.iconSlotWidth)).size,
  ).toBe(1)
  expect(
    new Set(platformCellAlignment.map((item) => item.iconCenterOffset)).size,
  ).toBe(1)
  expect(new Set(platformCellAlignment.map((item) => item.labelOffset)).size).toBe(
    1,
  )
  expect(new Set(platformCellAlignment.map((item) => item.gap)).size).toBe(1)
  expect(
    platformCellAlignment.every((item) => item.labelTextAlign === 'left'),
  ).toBe(true)

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
  await expect(page.getByRole('columnheader', { name: '开启' })).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: '分组' })).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: '登录状态' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '店铺状态' })).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: '今日订单' }),
  ).toHaveCount(0)
  await expect(page.getByText('今日 GMV')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(page.getByText('未分组')).toHaveCount(0)
  await expect(page.getByText('深圳-工作站-03 +2')).toBeVisible()
  await expect(page.getByText('批量分配分组')).toHaveCount(0)
  await expect(page.getByText('批量开启')).toHaveCount(0)
  await expect(page.getByText('批量关闭')).toHaveCount(0)
  await expect(page.getByText('批量删除')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)
  await expect(
    page.getByRole('row').filter({ hasText: '星河服饰旗舰店' }).getByText('已失效'),
  ).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: '海风家居生活馆' }).getByText('待验证'),
  ).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: '青禾食品旗舰店' }).getByText('有效'),
  ).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: '拾光数码工坊' }).getByText('未登录'),
  ).toBeVisible()

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
  await expect(
    platformNavigation.getByRole('button', { name: '抖店' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('星河服饰旗舰店')).toBeVisible()
  await expect(page.getByText('海风家居生活馆')).toHaveCount(0)

  await page.getByRole('button', { name: '拼多多', exact: true }).click()
  await expect(
    platformNavigation.getByRole('button', { name: '拼多多' }),
  ).toHaveAttribute('aria-pressed', 'true')
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
    const topbar = document
      .querySelector('.app-shell__topbar')
      ?.getBoundingClientRect()
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
    page.locator('.shop-session-card').getByText('已失效', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '配置账号与连接' }),
  ).toBeEnabled()
  await expect(page.getByText('登录会话', { exact: true })).toBeVisible()
  await expect(
    page.locator('.shop-session-card').getByText('已失效', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '验证会话' }),
  ).toBeEnabled()
  await expect(page.getByRole('button', { name: '重新登录' })).toBeVisible()
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
  await expect(page.getByText('平台店铺名称')).toBeVisible()
  await expect(page.getByText('platform-shop-fixture-001')).toBeVisible()
  await expect(page.getByText('执行设备', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('杭州-运营机-01').last()).toBeVisible()

  await page.getByRole('button', { name: '+ 绑定设备' }).click()
  await page.getByRole('dialog').last().getByRole('textbox').click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '上海-直播机-02' })
    .click()
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('上海-直播机-02').last()).toBeVisible()

  await page.getByRole('button', { name: '+ 绑定设备' }).click()
  await page.getByRole('dialog').last().getByRole('textbox').click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '深圳-工作站-03' })
    .click()
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('深圳-工作站-03').last()).toBeVisible()
  await page
    .locator('.shop-device-bindings__row')
    .filter({ hasText: '深圳-工作站-03' })
    .getByRole('button', { name: '解绑' })
    .click()
  await expect(
    page
      .locator('.shop-device-bindings__row')
      .filter({ hasText: '深圳-工作站-03' }),
  ).toHaveCount(0)
  await expect(
    page
      .locator('.shop-device-bindings__row')
      .filter({ hasText: '上海-直播机-02' }),
  ).toBeVisible()

  await page
    .locator('.shop-detail-header')
    .getByRole('button', { name: '编辑' })
    .click()
  await expect(page.getByText('编辑店铺', { exact: true })).toBeVisible()
  const editDialog = page.getByRole('dialog').last()
  await expect(editDialog.getByText('平台店铺名称')).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toHaveCount(0)
  await expect(editDialog.getByText('platform-shop-fixture-001')).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '查看' }).first().click()
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
  await expect(page.getByText('上海-直播机-02').last()).toBeVisible()
  await expect(page.getByText('杭州-运营机-01').last()).toBeVisible()
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

test('validates an invalid ShopSession and refreshes the compact drawer state', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '查看' }).first().click()

  await expect(
    page.locator('.shop-session-card').getByText('已失效'),
  ).toBeVisible()
  await expect(page.getByText('v3', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '验证会话' }).click()

  await expect(
    page.locator('.shop-session-card').getByText('有效'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: '重新登录' })).toHaveCount(0)
})

test('reuses Management Profile, shows recovery progress and refreshes version', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const attemptId = '00000000-0000-4000-8000-000000000011'
    window.desktop = {
      appearance: { setTitleBarTheme() {} },
      managementLogin: {
        async open() {
          return {
            attemptId,
            status: 'waiting',
            identity: null,
            sessionCaptured: false,
            cookieCount: 0,
            recovery: true,
            profileReused: true,
            message: '正在检查本机登录环境',
          }
        },
        async getStatus() {
          await new Promise((resolve) => window.setTimeout(resolve, 500))
          return {
            attemptId,
            status: 'identified',
            identity: {
              platform: 'douyin',
              platformShopId: 'platform-shop-fixture-001',
              shopDisplayName: '星河服饰旗舰店',
            },
            sessionCaptured: true,
            cookieCount: 12,
            recovery: true,
            profileReused: true,
            message: '已重新采集登录会话',
          }
        },
        async refresh() {
          return {
            shopId: 'shop-fixture-001',
            status: 'valid',
            sessionVersion: 4,
            validatedAt: '2026-08-22T00:20:00+08:00',
            cookieUpdatesApplied: 0,
            profileMappingWarning: null,
          }
        },
        async complete() {
          throw new Error('not used')
        },
        async close() {},
      },
    }
  })
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '查看' }).first().click()
  await page.getByRole('button', { name: '重新登录' }).click()

  await expect(page.getByText(/已复用本机登录环境/)).toBeVisible()
  await expect(page.getByText('v4', { exact: true })).toBeVisible()
  await expect(
    page.locator('.shop-session-card').getByText('有效'),
  ).toBeVisible()
})

test('persists the formal Shop enabled state in the list interaction', async ({
  page,
}) => {
  await page.goto('/#/shops')
  const row = page.getByRole('row').filter({ hasText: '星河服饰旗舰店' })
  await expect(row.getByText('已启用', { exact: true })).toBeVisible()

  await row.getByRole('button', { name: '停用', exact: true }).click()
  await expect(row.getByText('已停用', { exact: true })).toBeVisible()
  await row.getByRole('button', { name: '启用', exact: true }).click()
  await expect(row.getByText('已启用', { exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '自动化' })).toHaveCount(0)
})

test('confirms a single-shop soft removal and removes it from the normal list', async ({
  page,
}) => {
  await page.goto('/#/shops')
  const row = page.getByRole('row').filter({ hasText: '海风家居生活馆' })
  await row.getByRole('button', { name: '移除', exact: true }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('店铺：海风家居生活馆')
  await expect(dialog.getByText(/设备绑定将停用/)).toBeVisible()
  await expect(dialog.getByText(/登录凭证、Session/)).toBeVisible()
  await dialog.getByRole('button', { name: '确认移除' }).click()

  await expect(page.getByText('海风家居生活馆')).toHaveCount(0)
  await expect(page.getByText('批量移除')).toHaveCount(0)
})

test('surfaces a refresh lease conflict without opening a login window', async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.desktop = {
      appearance: { setTitleBarTheme() {} },
      managementLogin: {
        async open() {
          throw new Error('login window must not open after lease conflict')
        },
        async getStatus() {
          throw new Error('not used')
        },
        async complete() {
          throw new Error('not used')
        },
        async refresh() {
          throw new Error('not used')
        },
        async close() {},
      },
    }
  })
  await page.goto('/#/shops')
  const row = page.getByRole('row', { name: /云朵母婴专营店/ })
  await row.getByRole('button', { name: '查看' }).click()
  await page.getByRole('button', { name: '重新登录' }).click()

  await expect(page.getByText('该店铺登录会话正在恢复')).toBeVisible()
})

test('drives the Management Login onboarding through typed Electron state', async ({
  page,
}) => {
  await page.addInitScript(() => {
    let statusChecks = 0
    const attemptId = '00000000-0000-4000-8000-000000000001'
    window.desktop = {
      appearance: { setTitleBarTheme() {} },
      managementLogin: {
        async open() {
          return {
            attemptId,
            status: 'waiting',
            identity: null,
            sessionCaptured: false,
            cookieCount: 0,
            recovery: false,
            profileReused: false,
            message: '等待人工登录，系统会自动识别店铺',
          }
        },
        async getStatus() {
          statusChecks += 1
          return {
            attemptId,
            status: statusChecks > 0 ? 'identified' : 'waiting',
            identity: {
              platform: 'douyin',
              platformShopId: '987654321',
              shopDisplayName: '真实识别店铺',
            },
            sessionCaptured: true,
            cookieCount: 12,
            recovery: false,
            profileReused: false,
            message: '已自动识别店铺并采集登录会话，登录窗口已关闭',
          }
        },
        async complete() {
          return {
            shopId: '00000000-0000-4000-8000-000000000002',
            platformShopId: '987654321',
            shopDisplayName: '真实识别店铺',
            maskedIdentifier: '138****8888',
            sessionStatus: 'captured',
            sessionVersion: 1,
            sessionCapturedAt: '2026-08-21T12:00:00Z',
            profileMappingWarning:
              '服务器已完成店铺接入，但本机登录环境映射未保存；下次恢复需要重新登录',
          }
        },
        async refresh() {
          return {
            shopId: '00000000-0000-4000-8000-000000000002',
            status: 'valid',
            sessionVersion: 2,
            validatedAt: '2026-08-21T12:05:00Z',
            cookieUpdatesApplied: 0,
            profileMappingWarning: null,
          }
        },
        async close() {},
      },
    }
  })
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true })).toBeVisible()
  await expect(
    page.getByText('选择平台', { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByText('账号与密码', { exact: true })).toBeVisible()
  await expect(page.getByText('登录并识别', { exact: true })).toBeVisible()
  await expect(page.getByText('确认店铺', { exact: true })).toBeVisible()
  await expect(page.getByText('完成', { exact: true })).toBeVisible()
  await expect(page.getByText('登录成功后由平台自动识别')).toBeVisible()
  await expect(page.getByPlaceholder('请输入店铺名称')).toHaveCount(0)

  await page.locator('.n-drawer .n-base-selection').click()
  const options = page.locator('.n-base-select-option')
  await expect(options.filter({ hasText: '抖店' })).toBeVisible()
  await expect(options.filter({ hasText: '拼多多' })).toBeVisible()
  await expect(options.filter({ hasText: '拼多多' })).not.toHaveClass(/--disabled/)
  await expect(options.filter({ hasText: '淘宝' })).toHaveClass(/--disabled/)
  await expect(options.filter({ hasText: '视频号' })).toHaveClass(/--disabled/)
  await options.filter({ hasText: '抖店' }).click()
  await page.getByRole('button', { name: '下一步' }).click()

  await page
    .getByPlaceholder('手机号、邮箱、用户名或账号 ID')
    .fill('13812348888')
  await page.getByPlaceholder('请输入登录密码').fill('onboarding-password')
  await page.getByRole('button', { name: '下一步' }).click()

  await page.getByRole('button', { name: '打开浏览器登录' }).click()
  await expect(page.getByText('真实识别店铺', { exact: true })).toBeVisible()
  await expect(page.getByText('987654321', { exact: true })).toBeVisible()
  await expect(page.getByText('已采集', { exact: true })).toBeVisible()
  await expect(page.getByText('已识别', { exact: true })).toBeVisible()
  await expect(page.getByText('onboarding-password')).toHaveCount(0)
  await page.getByRole('button', { name: '完成接入' }).click()
  await expect(page.getByText('接入成功', { exact: true })).toBeVisible()
  await expect(page.getByText('138****8888')).toBeVisible()
  await expect(
    page.getByText('服务器已完成店铺接入，但本机登录环境映射未保存；下次恢复需要重新登录'),
  ).toBeVisible()
})

test('renders compact Shop and Device pages in light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByRole('region', { name: '筛选条件' })).toBeVisible()

  await page.getByText('自动化中心', { exact: true }).click()
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
    await expect(page.getByText('基本信息')).toBeVisible()
    const safeArea = await page.evaluate(() => {
      const topbar = document
        .querySelector('.app-shell__topbar')
        ?.getBoundingClientRect()
      const drawer = document
        .querySelector('.n-drawer')
        ?.getBoundingClientRect()
      return { topbarBottom: topbar?.bottom, drawerTop: drawer?.top }
    })
    expect(safeArea.drawerTop).toBe(safeArea.topbarBottom)
    await assertNoPageOverflow()
    await page.getByRole('button', { name: '关闭', exact: true }).click()
  })
}
