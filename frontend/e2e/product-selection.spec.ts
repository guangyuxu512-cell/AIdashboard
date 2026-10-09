import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const
async function settleTransitions(page: Page) {
  await expect
    .poll(() =>
      page
        .locator('body')
        .evaluate(
          (element) =>
            element
              .getAnimations({ subtree: true })
              .filter(
                (animation) =>
                  animation.playState === 'running' &&
                  animation.effect?.getTiming().iterations !== Infinity,
              ).length,
        ),
    )
    .toBe(0)
}
test.beforeEach(async ({ page }) => {
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
  await expect(rows).toHaveCount(10)
  await expect(page.getByText('共 32 条', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('columnheader', { name: '商品ID', exact: true }),
  ).toHaveCount(0)
  const title = rows.first().locator('td').nth(2).locator('.n-ellipsis')
  const fullTitle = 'Essence 纤长卷翘防水睫毛膏 浓密自然不晕染持久眼妆便携装'
  await expect(title).toHaveText(fullTitle)
  expect(
    await title.evaluate((element) => ({
      whiteSpace: getComputedStyle(element).whiteSpace,
      overflow: element.scrollWidth > element.clientWidth,
      height: element.getBoundingClientRect().height,
    })),
  ).toMatchObject({ whiteSpace: 'nowrap', overflow: true })
  await title.hover()
  await expect(
    page.locator('.n-popover').getByText(fullTitle, { exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: info.outputPath('long-title-tooltip.png'),
    animations: 'disabled',
  })
  await page.getByRole('columnheader', { name: '缩略图', exact: true }).hover()
  const body = page.locator('.n-data-table-base-table-body')
  await body.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await expect
    .poll(() =>
      rows
        .locator('.n-image img')
        .evaluateAll((images) =>
          images.every((image) => (image as HTMLImageElement).naturalWidth > 0),
        ),
    )
    .toBe(true)
  await body.evaluate((element) => {
    element.scrollTop = 0
  })
  await expect(
    page.getByRole('button', { name: '重试商品图片', exact: true }),
  ).toHaveCount(0)
  await expect(page.locator('.n-message')).toHaveCount(0)
  expect(
    await rows
      .first()
      .locator('.n-image img')
      .evaluate((image) => [
        getComputedStyle(image).width,
        getComputedStyle(image).height,
        getComputedStyle(image).objectFit,
      ]),
  ).toEqual(['80px', '80px', 'contain'])
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
      .getByRole('columnheader', { name: '缩略图', exact: true })
      .boundingBox()
    const scroll = page.locator('.n-data-table-base-table-body')
    await scroll.evaluate((element) => {
      element.scrollLeft = 1000
    })
    expect(
      (await page
        .getByRole('columnheader', { name: '缩略图', exact: true })
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
    const colors = await rows.first().evaluate((row) => {
      const plain = row.querySelector('td:nth-child(3)')!
      const missing = row.querySelector('.n-text')!
      return {
        body: getComputedStyle(plain).color,
        missing: getComputedStyle(missing).color,
        cell: getComputedStyle(plain).backgroundColor,
      }
    })
    expect(colors.body).not.toBe(colors.missing)
    await page.goto('/#/shops')
    const shopCell = page.locator('.n-data-table-tbody td').nth(1)
    await expect(shopCell).toBeVisible()
    await page.screenshot({
      path: info.outputPath(`${id}-shop-reference.png`),
      animations: 'disabled',
    })
    await expect
      .poll(() => shopCell.evaluate((cell) => getComputedStyle(cell).color))
      .toBe(colors.body)
    const colorPath = info.outputPath(`${id}-computed-candidate-colors.json`)
    await writeFile(colorPath, JSON.stringify(colors, null, 2))
    await info.attach(`${id}-computed-candidate-colors`, {
      path: colorPath,
      contentType: 'application/json',
    })
    await page.goto('/#/product-selection')
    await expect(rows).toHaveCount(10)
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
  await expect(rows.first()).toContainText(fullTitle)
  const date = page.getByRole('columnheader', {
    name: '首次上架日期',
    exact: true,
  })
  await date.click()
  await expect(rows.first()).toContainText('2026-09-28')
  await date.click()
  await expect(rows.first()).toContainText('2026-09-02')
  await page.locator('.n-pagination-item').filter({ hasText: /^2$/ }).click()
  await expect(rows).toHaveCount(10)
  await page
    .getByRole('textbox', { name: '搜索候选商品' })
    .fill('9087654321098765031')
  await expect(rows).toHaveCount(1)
  await expect(page.getByText('共 1 条', { exact: true })).toBeVisible()
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(page.locator('.n-drawer')).toContainText('短视频用户支付金额')
  await expect(page.locator('.n-drawer')).toContainText('单位未确认')
  for (const label of [
    '店铺',
    '类目',
    '价格带',
    '上架日期',
    '差评率',
    '屏蔽状态',
  ])
    await expect(page.locator('.n-drawer')).toContainText(label)
  await page.locator('.n-drawer-body-content-wrapper').evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await page.screenshot({
    path: info.outputPath('candidate-detail.png'),
    animations: 'disabled',
  })
  await page.locator('.n-drawer-header__close').click()
  await rows
    .first()
    .getByRole('button', { name: '采集资料', exact: true })
    .click()
  await expect(
    page.getByText('商品资料采集流程演示；未发起真实采集，未写入正式商品库', {
      exact: true,
    }),
  ).toBeVisible()
  await rows
    .first()
    .getByRole('button', { name: /^更多操作 / })
    .click()
  await page.locator('.n-dropdown').getByText('屏蔽', { exact: true }).click()
  await expect(rows).toHaveCount(0)
  await page.getByText('未屏蔽', { exact: true }).click()
  await page
    .locator('.n-base-select-menu')
    .getByText('已屏蔽', { exact: true })
    .click()
  await expect(rows).toHaveCount(1)
  await rows
    .first()
    .getByRole('button', { name: /^更多操作 / })
    .click()
  await page.locator('.n-dropdown').getByText('恢复', { exact: true }).click()
  await expect(rows).toHaveCount(0)
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(rows).toHaveCount(10)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  expect(apiRequests).toEqual([])
})

test('batch demo selects only the current page, rejects empty selection and guards rapid clicks', async ({
  page,
}, info) => {
  await page.goto('/#/product-selection')
  const rows = page.locator('.n-data-table-tbody .n-data-table-tr')
  const batch = page.getByRole('button', { name: '批量采集资料', exact: true })
  await expect(rows).toHaveCount(10)
  await expect(batch).toBeDisabled()
  await page.locator('.n-data-table-thead').getByRole('checkbox').check()
  await expect(
    page.getByText('已选择 10 项 · 全选仅当前页', { exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: info.outputPath('batch-selected-current-page.png'),
    animations: 'disabled',
  })
  await batch.evaluate((button) => {
    ;(button as HTMLButtonElement).click()
    ;(button as HTMLButtonElement).click()
  })
  await expect(
    page.getByText('资料采集演示完成 10 项，失败 0 项；未发起真实采集', {
      exact: true,
    }),
  ).toHaveCount(1)
  await expect(batch).toBeDisabled()
  await expect(
    page.getByText('已选择 0 项 · 全选仅当前页', { exact: true }),
  ).toBeVisible()
  await page.locator('.n-data-table-thead').getByRole('checkbox').check()
  await page.locator('.n-pagination-item').filter({ hasText: /^2$/ }).click()
  await expect(rows.first()).toContainText('演示商品 11')
  await expect(batch).toBeDisabled()
  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(rows).toHaveCount(10)
  await expect(rows.first()).toContainText('Essence 纤长卷翘防水睫毛膏')
  await expect(page.locator('.n-message')).toHaveCount(0)
  await page.screenshot({
    path: info.outputPath('candidate-wide-1920.png'),
    animations: 'disabled',
  })
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  await expect(drawer).toContainText('未屏蔽')
  await expect(drawer.getByText('—', { exact: true })).toHaveCount(4)
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  const copy = drawer.getByRole('button', {
    name: '复制商品ID 9087654321098765000',
    exact: true,
  })
  await expect(copy).toHaveText('')
  await expect(copy.locator('svg')).toHaveCount(1)
  await copy.click()
  await expect(page.getByText('商品ID已复制', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    '9087654321098765000',
  )
  await expect(drawer.locator('.n-image img')).toBeVisible()
  await drawer.locator('.n-image').click()
  await expect(page.locator('.n-image-preview-container')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  await expect(drawer).toContainText('未屏蔽')
  await expect(drawer).toContainText('1000–5000')
  await settleTransitions(page)
  await page.screenshot({
    path: info.outputPath('detail-fields-null-wide.png'),
    animations: 'disabled',
  })
  await drawer.locator('.n-drawer-body-content-wrapper').evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await page.screenshot({
    path: info.outputPath('detail-fields-null-wide-bottom.png'),
    animations: 'disabled',
  })
})
test('exception-only: batch partial failure preserves failed selection and all item feedback', async ({
  page,
}, info) => {
  // Only intercept the development Mock module; no proposed Backend endpoint or production hook.
  await page.route(
    '**/src/features/product-selection/api/selection-mock-handlers.ts*',
    async (route) => {
      const response = await route.fetch()
      const source = await response.text()
      const marker = 'function collect(id) {'
      expect(source).toContain(marker)
      await route.fulfill({
        response,
        body: source.replace(
          marker,
          `${marker}\n if (id === "candidate-001") throw new Error("受控演示采集失败");`,
        ),
      })
    },
  )
  await page.goto('/#/product-selection')
  const rows = page.locator('.n-data-table-tbody .n-data-table-tr')
  await expect(rows).toHaveCount(10)
  await rows.nth(0).getByRole('checkbox').check()
  await rows.nth(1).getByRole('checkbox').check()
  await rows.nth(2).getByRole('checkbox').check()
  await page.getByRole('button', { name: '批量采集资料', exact: true }).click()
  await expect(
    page.getByText('资料采集演示完成 2 项，失败 1 项；未发起真实采集', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByText('9087654321098765001：受控演示采集失败', { exact: true }),
  ).toBeVisible()
  await expect(rows.nth(0).getByRole('checkbox')).not.toBeChecked()
  await expect(rows.nth(1).getByRole('checkbox')).toBeChecked()
  await expect(rows.nth(2).getByRole('checkbox')).not.toBeChecked()
  await expect(
    page.getByText('已选择 1 项 · 全选仅当前页', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.n-message')).toHaveCount(0)
  await page.screenshot({
    path: info.outputPath('batch-partial-failure.png'),
    animations: 'disabled',
  })
})

test('strategy: right drawer, categories/all, retrieval without saving, validation, optional schedule, Baiying boundary', async ({
  page,
}, info) => {
  test.setTimeout(90000)
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
    drawer
      .locator('.n-form-item')
      .filter({
        has: page.locator('.n-form-item-label', {
          hasText: new RegExp(`^${label}$`),
        }),
      })
      .last()
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
  await expect(field('日期').getByRole('radio')).toHaveCount(4)
  await expect(
    field('日期').getByRole('radio', { name: '实时', exact: true }),
  ).toBeChecked()
  await expect(field('日期').locator('.n-select')).toHaveCount(0)
  await expect(drawer.getByText('更多', { exact: true })).toHaveCount(0)
  await drawer.getByRole('textbox', { name: '策略名称' }).click()
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText('演示获取完成；未向平台请求，未启动采集任务', {
      exact: true,
    }),
  ).toBeVisible()
  await drawer
    .getByRole('textbox', { name: '策略名称' })
    .fill('前端验证策略长名称 A，不启动后台任务')
  await field('价格').getByText('自定义', { exact: true }).click()
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
  await field('每日时间').getByRole('textbox').fill('10:00')
  await field('每日时间').getByRole('textbox').press('Enter')
  await field('策略状态').click()
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(row).toContainText('每日 10:00（演示）')
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(field('每日时间').getByRole('textbox')).toHaveValue('10:00')
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
    .locator('.n-collapse-item')
    .filter({
      has: page.locator('.n-collapse-item__header-main', {
        hasText: '短视频榜单',
      }),
    })
    .locator('.n-collapse-item__header-main')
    .click()
  await expect(field('价格大于').getByRole('textbox')).toBeHidden()
  await drawer
    .locator('.n-collapse-item__header-main')
    .filter({ hasText: '巨量百应' })
    .click()
  await drawer.getByRole('checkbox', { name: '选择巨量百应' }).check()
  await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).uncheck()
  await expect(drawer.getByText('待接入', { exact: true })).toHaveCount(0)
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText('巨量百应获取尚未接入', { exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: info.outputPath('baiying-empty-conditions.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).check()
  await drawer
    .locator('.n-collapse-item__header-main')
    .filter({ hasText: '短视频榜单' })
    .click()
  await expect(field('价格大于').getByRole('textbox')).toHaveValue('10')
  await expect(field('价格小于').getByRole('textbox')).toHaveValue('50')
  await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
  await expect(row).toContainText('短视频榜单、巨量百应')
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(
    drawer.getByRole('checkbox', { name: '选择巨量百应' }),
  ).toBeChecked()
  await expect(field('价格小于').getByRole('textbox')).toHaveValue('50')
  await expect(field('定时执行').getByRole('switch')).toHaveCount(1)
  await expect(field('策略状态').getByRole('switch')).toHaveCount(1)
  await drawer.getByRole('button', { name: '立即获取', exact: true }).click()
  await expect(
    page.getByText(
      '演示获取完成；未向平台请求，未启动采集任务；巨量百应获取尚未接入',
      { exact: true },
    ),
  ).toBeVisible()
  await expect(page.locator('.n-message')).toHaveCount(0)
  for (const [id, label] of themes) {
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await drawer
      .locator('.n-collapse-item__header-main')
      .filter({ hasText: '短视频榜单' })
      .click()
    await drawer
      .locator('.n-collapse-item__header-main')
      .filter({ hasText: '巨量百应' })
      .click()
    await expect(
      drawer.getByRole('checkbox', { name: '选择巨量百应' }),
    ).toBeInViewport()
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${id}-multichannel-overview.png`),
      animations: 'disabled',
    })
    await drawer
      .locator('.n-collapse-item__header-main')
      .filter({ hasText: '短视频榜单' })
      .click()
    await drawer
      .locator('.n-drawer-body-content-wrapper')
      .evaluate((element) => {
        element.scrollTop = 0
      })
    await expect(
      field('日期').getByRole('radio', { name: '近30天', exact: true }),
    ).toBeVisible()
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${id}-multichannel.png`),
      animations: 'disabled',
    })
    await field('品牌').locator('.n-select').click()
    await expect(page.locator('.n-base-select-menu')).toBeVisible()
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${id}-dropdown.png`),
      animations: 'disabled',
    })
    const colors = await drawer.evaluate((element) => {
      const label = element.querySelector('.n-form-item-label')!
      const input = element.querySelector('.n-input input')!
      const panel = element.querySelector('.n-drawer-body')!
      return {
        label: getComputedStyle(label).color,
        input: getComputedStyle(input).color,
        background: getComputedStyle(panel).backgroundColor,
      }
    })
    const colorPath = info.outputPath(`${id}-computed-drawer-colors.json`)
    await writeFile(colorPath, JSON.stringify(colors, null, 2))
    await info.attach(`${id}-computed-drawer-colors`, {
      path: colorPath,
      contentType: 'application/json',
    })
    await drawer.getByRole('textbox', { name: '策略名称' }).click()
    await expect(field('价格小于').getByRole('textbox')).toHaveValue('50')
    await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).uncheck()
    await expect(field('价格小于').getByRole('textbox')).toBeDisabled()
    await page.screenshot({
      path: info.outputPath(`${id}-disabled-conditions.png`),
      animations: 'disabled',
    })
    await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).check()
    await expect(field('价格小于').getByRole('textbox')).toHaveValue('50')
    await drawer
      .locator('.n-drawer-body-content-wrapper')
      .evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
    await page.screenshot({
      path: info.outputPath(`${id}-multichannel-scroll.png`),
      animations: 'disabled',
    })
  }
  await page.setViewportSize({ width: 1920, height: 1080 })
  await drawer.locator('.n-drawer-body-content-wrapper').evaluate((element) => {
    element.scrollTop = 0
  })
  await settleTransitions(page)
  const pairs = [
    ['请求店铺', '达人账号'],
    ['日期', '品牌'],
    ['价格大于', '价格小于'],
    ['起始排名', '结束排名'],
  ]
  for (const [left, right] of pairs) {
    const leftBounds = await field(left!).boundingBox()
    const rightBounds = await field(right!).boundingBox()
    expect(Math.abs(leftBounds!.y - rightBounds!.y)).toBeLessThan(2)
    expect(rightBounds!.x).toBeGreaterThan(leftBounds!.x)
  }
  for (const label of [
    '策略名称',
    '价格大于',
    '价格小于',
    '起始排名',
    '结束排名',
  ]) {
    const labelBounds = await field(label)
      .locator('.n-form-item-label')
      .boundingBox()
    const inputBounds = await field(label).getByRole('textbox').boundingBox()
    expect(inputBounds!.x).toBeGreaterThan(labelBounds!.x)
    expect(
      Math.abs(
        inputBounds!.y +
          inputBounds!.height / 2 -
          labelBounds!.y -
          labelBounds!.height / 2,
      ),
    ).toBeLessThan(2)
  }
  await page.screenshot({
    path: info.outputPath('compact-strategy-wide-1920.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
})

test('date shortcuts: four exclusive relative periods, Mock ranges, reread, cancel and disabled retention', async ({
  page,
}, info) => {
  test.setTimeout(90000)
  await page.goto('/#/product-selection?tab=selection-strategy')
  const row = page
    .locator('.n-data-table-tbody .n-data-table-tr')
    .filter({ hasText: '短视频热销观察' })
  const drawer = page.locator('.n-drawer')
  const field = (label: string) =>
    drawer
      .locator('.n-form-item')
      .filter({
        has: page.locator('.n-form-item-label', {
          hasText: new RegExp(`^${label}$`),
        }),
      })
      .last()
  const date = field('日期')
  const header = () =>
    drawer
      .locator('.n-collapse-item__header-main')
      .filter({ hasText: '短视频榜单' })
  const periods = [
    ['实时', '2026-10-08 00:00–12:00'],
    ['近1天', '2026-10-07 00:00–23:59'],
    ['近7天', '2026-10-01–2026-10-07'],
    ['近30天', '2026-09-08–2026-10-07'],
  ] as const
  for (const [label, range] of periods) {
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(date.getByRole('radio')).toHaveCount(4)
    await date.getByText(label, { exact: true }).click()
    await expect(date.locator('input[type="radio"]:checked')).toHaveCount(1)
    await expect(date).toContainText(`Mock 示例区间：${range}`)
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`period-${label}.png`),
      animations: 'disabled',
    })
    await drawer.getByRole('button', { name: '保存策略', exact: true }).click()
    await expect(drawer).toHaveCount(0)
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(
      date.getByRole('radio', { name: label, exact: true }),
    ).toBeChecked()
    await expect(date).toContainText(range)
    await header().click()
    await expect(date).toBeHidden()
    await header().click()
    await expect(
      date.getByRole('radio', { name: label, exact: true }),
    ).toBeChecked()
    // Unsaved edits must not alter the source strategy.
    await date
      .getByText(label === '实时' ? '近7天' : '实时', { exact: true })
      .click()
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(
      date.getByRole('radio', { name: label, exact: true }),
    ).toBeChecked()
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
  }
  for (const [id, label] of themes) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await expect(
      date.getByRole('radio', { name: '近30天', exact: true }),
    ).toBeChecked()
    await settleTransitions(page)
    const radios = await date.locator('.n-radio-button').all()
    const bounds = await Promise.all(radios.map((radio) => radio.boundingBox()))
    const brand = await field('品牌').boundingBox()
    await writeFile(
      info.outputPath(`${id}-date-layout.json`),
      JSON.stringify({ bounds, brand }, null, 2),
    )
    await page.screenshot({
      path: info.outputPath(`${id}-date-1366.png`),
      animations: 'disabled',
    })
    for (const radio of radios) await expect(radio).toBeInViewport()
    expect(bounds.every((box) => Math.abs(box!.y - bounds[0]!.y) < 2)).toBe(
      true,
    )
    expect(bounds[3]!.x + bounds[3]!.width).toBeLessThanOrEqual(brand!.x)
    const preview = await date.locator('.n-text').boundingBox()
    expect(preview!.y).toBeGreaterThanOrEqual(bounds[0]!.y + bounds[0]!.height)
    await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).uncheck()
    await expect(date.locator('input[type="radio"]:disabled')).toHaveCount(4)
    await date
      .getByRole('radio', { name: '实时', exact: true })
      .dispatchEvent('click')
    await expect(
      date.getByRole('radio', { name: '近30天', exact: true }),
    ).toBeChecked()
    await page.screenshot({
      path: info.outputPath(`${id}-date-disabled.png`),
      animations: 'disabled',
    })
    await drawer.getByRole('checkbox', { name: '选择短视频榜单' }).check()
    await expect(
      date.getByRole('radio', { name: '近30天', exact: true }),
    ).toBeChecked()
    await drawer.getByRole('button', { name: '取消', exact: true }).click()
  }
  await page.setViewportSize({ width: 1920, height: 1080 })
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await settleTransitions(page)
  await page.screenshot({
    path: info.outputPath('date-wide-1920.png'),
    animations: 'disabled',
  })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
})

test('exception-only: external image failure, no authentication headers and explicit recovery', async ({
  page,
}, info) => {
  let failures = 0
  await page.route('https://selection-image.invalid/**', async (route) => {
    const headers = await route.request().allHeaders()
    expect(headers.authorization).toBeUndefined()
    expect(headers['x-team-id']).toBeUndefined()
    failures++
    await route.abort()
  })
  await page.goto('/#/product-selection')
  const firstImage = page.locator('.n-data-table-tbody .n-image img').first()
  await expect(firstImage).toBeVisible()
  await firstImage.evaluate((image) => {
    ;(image as HTMLImageElement).src =
      'https://selection-image.invalid/photo.webp'
  })
  const retry = page.getByRole('button', { name: '重试商品图片', exact: true })
  await expect(retry).toBeVisible()
  await expect.poll(() => failures).toBe(1)
  await expect(retry).toBeVisible()
  await page.screenshot({
    path: info.outputPath('image-failure.png'),
    animations: 'disabled',
  })
  await retry.click()
  await expect(retry).toHaveCount(0)
  await expect
    .poll(() =>
      page
        .locator('.n-data-table-tbody .n-image img')
        .first()
        .evaluate((image) => (image as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0)
  await page
    .locator('.n-data-table-tbody .n-data-table-tr')
    .first()
    .getByRole('button', { name: '详情', exact: true })
    .click()
  await page.locator('.n-drawer .n-image img').evaluate((image) => {
    ;(image as HTMLImageElement).src =
      'https://selection-image.invalid/detail.webp'
  })
  const detailRetry = page
    .locator('.n-drawer')
    .getByRole('button', { name: '重试商品图片', exact: true })
  await expect(detailRetry).toBeVisible()
  await page.screenshot({
    path: info.outputPath('detail-image-failure.png'),
    animations: 'disabled',
  })
  await detailRetry.click()
  await expect(detailRetry).toHaveCount(0)
})

test('candidate structure, merchant identity and themed action hierarchy: four actual rendered themes', async ({
  page,
}, info) => {
  test.setTimeout(120000)
  await page.goto('/#/product-selection')
  const rows = page.locator('.n-data-table-tbody .n-data-table-tr')
  const batch = page.getByRole('button', { name: '批量采集资料', exact: true })
  const refresh = page.getByRole('button', { name: '刷新列表', exact: true })
  const detail = page.locator('.n-drawer')
  await expect(rows).toHaveCount(10)
  const headers = (await page.locator('.n-data-table-th').allTextContents())
    .map((label) => label.trim())
    .filter(Boolean)
  expect(headers).toEqual([
    '缩略图',
    '商品标题',
    '店铺名',
    '类目',
    '榜单排名',
    '发现情况',
    '价格／价格带',
    '差评率',
    '首次上架日期',
    '采集状态',
    '操作',
  ])
  await expect(rows.nth(1)).toContainText('上升 2')
  await expect(rows.nth(3)).toContainText('离开监控范围')
  await expect(rows.nth(3)).not.toContainText('上升')
  await expect(rows.nth(4)).toContainText('新进入监控范围')
  await expect(page.getByText(/榜单：短视频商品榜单/)).toContainText(
    '监控范围：1～200 名',
  )
  const colorEvidence = []
  for (const [id, label] of themes) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id)
    await expect(page.locator('.n-dropdown')).toBeHidden()
    await expect(batch).toBeDisabled()
    const disabledColors = await batch.evaluate((element) => ({
      text: getComputedStyle(element).color,
      background: getComputedStyle(element).backgroundColor,
    }))
    expect(disabledColors.text).not.toBe(disabledColors.background)
    await rows.first().getByRole('checkbox').check()
    await expect(batch).toBeEnabled()
    await settleTransitions(page)
    const primaryColors = await batch.evaluate((element) => ({
      text: getComputedStyle(element).color,
      background: getComputedStyle(element).backgroundColor,
    }))
    expect(primaryColors.background).not.toBe(disabledColors.background)
    const secondaryColors = await refresh.evaluate((element) => ({
      text: getComputedStyle(element).color,
      background: getComputedStyle(element).backgroundColor,
      border: getComputedStyle(element.querySelector('.n-button__border')!)
        .borderColor,
    }))
    const linkColor = await rows
      .first()
      .getByRole('button', { name: '详情', exact: true })
      .evaluate((element) => getComputedStyle(element).color)
    const tokenColor = await page.evaluate(() => {
      const probe = document.createElement('span')
      probe.style.color = 'var(--text-link)'
      document.body.append(probe)
      const color = getComputedStyle(probe).color
      probe.remove()
      return color
    })
    expect(linkColor).toBe(tokenColor)
    expect(secondaryColors.background).not.toBe(primaryColors.background)
    colorEvidence.push({
      theme: id,
      disabledColors,
      primaryColors,
      secondaryColors,
      linkColor,
    })
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${id}-candidate-final.png`),
      animations: 'disabled',
    })
    await rows.first().getByRole('checkbox').uncheck()
    await rows
      .first()
      .getByRole('button', { name: '详情', exact: true })
      .click()
    await expect(detail).toContainText('商品所属商家')
    await expect(detail).toContainText('轻盈美妆示例店')
    await expect(detail).toContainText('请求罗盘使用的自有店铺')
    await expect(detail).toContainText('星河服饰旗舰店')
    await expect(
      detail.getByRole('button', { name: '查看源商品', exact: true }),
    ).toHaveCount(0)
    for (const label of [
      '短视频用户支付金额',
      '短视频点击次数',
      '短视频成交件数',
      '带货视频数',
    ])
      await expect(detail).toContainText(label)
    await expect(detail).not.toContainText('近30天销量')
    await expect(
      detail.getByRole('button', { name: '采集资料', exact: true }),
    ).toBeInViewport()
    await expect(
      detail.getByRole('button', { name: '更新罗盘指标', exact: true }),
    ).toBeInViewport()
    await settleTransitions(page)
    await page.screenshot({
      path: info.outputPath(`${id}-detail-final.png`),
      animations: 'disabled',
    })
    await detail
      .locator('.n-drawer-body-content-wrapper')
      .evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
    await page.screenshot({
      path: info.outputPath(`${id}-detail-metrics-final.png`),
      animations: 'disabled',
    })
    await detail.getByRole('button', { name: '关闭', exact: true }).click()
  }
  await writeFile(
    info.outputPath('action-colors-four-themes.json'),
    JSON.stringify(colorEvidence, null, 2),
  )
  await rows.first().getByRole('button', { name: '详情', exact: true }).click()
  await detail
    .getByRole('button', { name: '标记为竞品店铺', exact: true })
    .click()
  await expect(
    detail.getByRole('button', { name: '已标记竞品店铺', exact: true }),
  ).toBeDisabled()
  await detail
    .getByRole('button', { name: '更新罗盘指标', exact: true })
    .click()
  await expect(
    page.getByText('罗盘指标更新流程演示；未向平台请求', { exact: true }),
  ).toBeVisible()
  await detail.getByRole('button', { name: '采集资料', exact: true }).click()
  await expect(detail).toContainText('已演示采集')
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(rows.first()).toContainText('已演示采集')
  await refresh.click()
  await expect(rows).toHaveCount(10)
  await expect(rows.first()).toContainText('已演示采集')
})
