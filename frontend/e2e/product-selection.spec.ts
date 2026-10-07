import { expect, test } from '@playwright/test'

const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const
test.beforeEach(async ({ page }) => {
  await page.route('https://selection-image.invalid/**', async (route) => {
    const headers = await route.request().allHeaders()
    expect(headers.authorization).toBeUndefined()
    expect(headers['x-team-id']).toBeUndefined()
    await route.abort()
  })
  await page.setViewportSize({ width: 1366, height: 768 })
})
test('candidate pool: four themes, centered fixed columns, IDs, full sort/pagination, preview and block/restore', async ({
  page,
}, info) => {
  const apiRequests: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/'))
      apiRequests.push(request.url())
  })
  await page.goto('/#/product-selection')
  const rows = page.locator('.n-data-table-tbody .n-data-table-tr')
  await expect(rows).toHaveCount(20)
  await expect(page.getByText('共 32 条', { exact: true })).toBeVisible()
  await expect(rows.first()).toContainText('908765432109876543210000')
  await expect(
    page.getByRole('button', { name: '重试商品图片', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '重试商品图片', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '重试商品图片', exact: true }),
  ).toBeVisible()
  for (const [id, label] of themes) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id)
    await expect(page.locator('.n-dropdown')).toBeHidden()
    expect(
      await page
        .locator('.n-data-table-th, .n-data-table-td')
        .evaluateAll((elements) =>
          elements.every(
            (element) => getComputedStyle(element).textAlign === 'center',
          ),
        ),
    ).toBe(true)
    const before = await page
      .getByRole('columnheader', { name: '店铺名', exact: true })
      .boundingBox()
    const scroll = page.locator('.n-data-table-base-table-body')
    await scroll.evaluate((element) => {
      element.scrollLeft = 1000
    })
    expect(
      (await page
        .getByRole('columnheader', { name: '店铺名', exact: true })
        .boundingBox())!.x,
    ).toBe(before!.x)
    await expect(
      page.getByRole('columnheader', { name: '操作', exact: true }),
    ).toBeInViewport()
    await page.screenshot({
      path: info.outputPath(`${id}-candidate-scrolled.png`),
      animations: 'disabled',
    })
    await scroll.evaluate((element) => {
      element.scrollLeft = 0
    })
    await page.screenshot({
      path: info.outputPath(`${id}-candidate.png`),
      animations: 'disabled',
    })
  }
  await rows.first().locator('.n-image').click()
  await expect(page.locator('.n-image-preview-container')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.n-image-preview-container')).toBeHidden()
  const rate = page.getByRole('columnheader', { name: '差评率', exact: true })
  await rate.click()
  await expect(rows.first()).toContainText('9.00%')
  await rate.click()
  await expect(rows.first()).toContainText('0.00%')
  await rate.click()
  await expect(rows.first()).toContainText('908765432109876543210000')
  const date = page.getByRole('columnheader', { name: '上架日期', exact: true })
  await date.click()
  await expect(rows.first()).toContainText('2026-09-28')
  await date.click()
  await expect(rows.first()).toContainText('2026-09-02')
  await page.locator('.n-pagination-item').filter({ hasText: /^2$/ }).click()
  await expect(rows).toHaveCount(12)
  await page
    .getByRole('textbox', { name: '搜索候选商品' })
    .fill('908765432109876543210031')
  await expect(rows).toHaveCount(1)
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(page.locator('.n-drawer')).toContainText('短视频用户支付金额')
  await expect(page.locator('.n-drawer')).toContainText('单位未确认')
  await page.screenshot({
    path: info.outputPath('candidate-detail.png'),
    animations: 'disabled',
  })
  await page.locator('.n-drawer-header__close').click()
  await rows
    .first()
    .getByRole('button', { name: '采集入库', exact: true })
    .click()
  await expect(
    page.getByText('采集入库流程演示；未写入正式商品库', { exact: true }),
  ).toBeVisible()
  await rows.first().getByRole('button', { name: '屏蔽', exact: true }).click()
  await expect(rows).toHaveCount(0)
  await page.getByText('未屏蔽', { exact: true }).click()
  await page
    .locator('.n-base-select-menu')
    .getByText('已屏蔽', { exact: true })
    .click()
  await expect(rows).toHaveCount(1)
  await rows.first().getByRole('button', { name: '恢复', exact: true }).click()
  await expect(rows).toHaveCount(0)
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(rows).toHaveCount(20)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  expect(apiRequests).toEqual([])
})
test('strategy: right drawer, categories/all, retrieval without saving, validation, optional schedule, Baiying boundary', async ({
  page,
}, info) => {
  await page.goto('/#/product-selection?tab=selection-strategy')
  await page.getByRole('button', { name: '达人登录', exact: true }).click()
  await expect(
    page.getByText('达人登录尚未接入', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.n-message')).toHaveCount(0)
  for (const [id, label] of themes) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('.n-dropdown')).toBeHidden()
    await page.screenshot({
      path: info.outputPath(`${id}-strategies.png`),
      animations: 'disabled',
    })
    await page.getByRole('button', { name: '新建策略', exact: true }).click()
    const drawer = page.locator('.n-drawer')
    await expect(drawer).toContainText('请求店铺')
    await expect(
      drawer.getByRole('button', { name: '达人登录', exact: true }),
    ).toHaveCount(0)
    await expect
      .poll(async () => {
        const box = await drawer.boundingBox()
        return Math.round(box!.x + box!.width)
      })
      .toBe(1366)
    await page.screenshot({
      path: info.outputPath(`${id}-strategy-drawer.png`),
      animations: 'disabled',
    })
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
  }
  await page.getByRole('button', { name: '新建策略', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  const field = (label: string) =>
    drawer.locator('.n-form-item').filter({
      has: page.locator('.n-form-item-label', {
        hasText: new RegExp(`^${label}$`),
      }),
    })
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(
    drawer.getByText('请选择请求店铺', { exact: true }),
  ).toBeVisible()
  await drawer.locator('.n-select').nth(0).click()
  await page
    .locator('.n-base-select-menu')
    .getByText('星河服饰旗舰店', { exact: true })
    .click()
  await drawer.locator('.n-select').nth(1).click()
  await page
    .locator('.n-base-select-menu')
    .getByText('演示达人 A', { exact: true })
    .click()
  await drawer.locator('.n-cascader').click()
  await page
    .locator('.n-cascader-menu')
    .getByText('服饰', { exact: true })
    .click()
  await page
    .locator('.n-cascader-menu')
    .getByText('全部', { exact: true })
    .click()
  await expect(drawer.locator('.n-cascader')).toContainText('全部')
  await drawer
    .getByRole('navigation', { name: '榜单日期' })
    .getByRole('button', { name: '更多', exact: true })
    .click()
  await expect(
    page.getByText('更多日期选项尚未确认', { exact: true }),
  ).toBeVisible()
  await expect(
    drawer
      .getByRole('navigation', { name: '榜单日期' })
      .getByRole('button', { name: '实时', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText('演示获取完成；未向平台请求，未启动采集任务', {
      exact: true,
    }),
  ).toBeVisible()
  await drawer
    .getByRole('textbox', { name: '策略名称' })
    .fill('前端验证策略长名称 A，不启动后台任务')
  await drawer
    .getByRole('navigation', { name: '价格条件' })
    .getByRole('button', { name: '自定义', exact: true })
    .click()
  await field('价格大于').getByRole('textbox').fill('10')
  await field('价格小于').getByRole('textbox').fill('5')
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(
    drawer.getByText('价格小于须大于价格大于', { exact: true }),
  ).toBeVisible()
  await field('价格小于').getByRole('textbox').fill('50')
  await field('定时执行').getByRole('switch').click()
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  await expect(page.getByText('共 3 条', { exact: true })).toBeVisible()
  const row = page
    .locator('.n-data-table-tbody .n-data-table-tr')
    .filter({ hasText: '前端验证策略长名称 A' })
  await expect(row).toContainText('每小时（演示）')
  await row.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(row).toContainText('演示获取 4 项')
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '采集任务', exact: true })
    .click()
  await expect(
    page.getByText('采集任务功能待接入', { exact: true }),
  ).toBeVisible()
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '选品策略', exact: true })
    .click()
  await expect(row).toContainText('演示获取 4 项')
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(drawer.getByRole('textbox', { name: '策略名称' })).toHaveValue(
    '前端验证策略长名称 A，不启动后台任务',
  )
  await field('执行频率').locator('.n-select').click()
  await page
    .locator('.n-base-select-menu')
    .getByText('每日', { exact: true })
    .click()
  await drawer.getByRole('textbox', { name: '每日时间' }).fill('10:00')
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(row).toContainText('每日 10:00（演示）')
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(drawer.getByRole('textbox', { name: '每日时间' })).toHaveValue(
    '10:00',
  )
  await expect(page.locator('.n-message')).toHaveCount(0)
  await drawer.locator('.n-drawer-body-content-wrapper').evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await page.screenshot({
    path: info.outputPath('midnight-strategy-configured-scroll.png'),
    animations: 'disabled',
  })
  await drawer.locator('.n-drawer-body-content-wrapper').evaluate((element) => {
    element.scrollTop = 0
  })
  await page.screenshot({
    path: info.outputPath('midnight-strategy-configured.png'),
    animations: 'disabled',
  })
  await drawer
    .getByRole('navigation', { name: '选品渠道' })
    .getByRole('button', { name: '巨量百应', exact: true })
    .click()
  await expect(drawer.locator('.n-cascader')).toHaveCount(0)
  await expect(drawer.getByText('待接入', { exact: true })).toHaveCount(0)
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText('巨量百应获取尚未接入', { exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: info.outputPath('baiying-empty-conditions.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
})
