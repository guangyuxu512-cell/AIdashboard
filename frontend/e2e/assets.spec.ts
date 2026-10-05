import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

test('manages image assets with the compact management pattern', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/shops')
  await expect(
    page.getByRole('columnheader', { name: '店铺名称' }),
  ).toBeVisible()
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await expect(nav.getByText('资料库', { exact: true })).toHaveCount(0)
  // The hidden standalone navigation does not remove the authorized route.
  await page.goto('/#/assets')

  await expect(page).toHaveURL(/#\/assets$/)
  await expect(page.getByLabel('当前位置')).toContainText('资料库')
  await expect(page.getByPlaceholder('搜索图片文件名')).toBeVisible()
  await expect(page.getByRole('button', { name: '上传图片' })).toBeVisible()
  await expect(page.getByText('test-01.jpg', { exact: true })).toBeVisible()
  await expect(page.getByText('test-02.png', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '切换主题' }).click()
  await page
    .locator('.n-dropdown')
    .getByText('石墨浅色', { exact: true })
    .click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText('午夜青', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.locator('input[type="file"]').setInputFiles({
    name: 'product-detail.png',
    mimeType: 'image/png',
    buffer: Buffer.from('fixture-image'),
  })
  await expect(page.getByText('已上传 1 张图片')).toBeVisible()
  await expect(
    page.getByText('product-detail.png', { exact: true }),
  ).toBeVisible()

  const row = page.getByRole('row').filter({ hasText: 'product-detail.png' })
  await row.getByRole('button', { name: '删除' }).click()
  const deleteDialog = page.getByRole('dialog').filter({ hasText: '删除图片' })
  await expect(deleteDialog.getByText(/product-detail\.png/)).toBeVisible()
  await deleteDialog.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('图片已删除')).toBeVisible()
  await expect(
    page.getByText('product-detail.png', { exact: true }),
  ).toHaveCount(0)

  const layout = await page.evaluate(() => ({
    documentOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    bodyOverflow: document.body.scrollWidth > document.body.clientWidth,
  }))
  expect(layout).toEqual({ documentOverflow: false, bodyOverflow: false })
  expect(runtimeErrors).toEqual([])
})

test('hides standalone assets for a team member while retaining route and AI materials', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await page.getByLabel('内部登录账号').fill('operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/shops$/)
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await expect(nav.getByText('资料库', { exact: true })).toHaveCount(0)
  await expect(nav.getByText('AI工作台', { exact: true })).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('team-member-hidden-assets.png'),
    animations: 'disabled',
  })
  await page.goto('/#/assets')
  await expect(page.getByPlaceholder('搜索图片文件名')).toBeVisible()
  await expect(page.getByText('test-01.jpg', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByPlaceholder('搜索图片文件名')).toBeVisible()
  await expect(page.getByLabel('当前位置')).toContainText('资料库')
  await page.goto('/#/ai-workbench/assets?visualMock=1')
  await expect(
    page
      .getByRole('navigation', { name: 'AI 功能入口' })
      .getByRole('button', { name: '素材库', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('region', { name: '产品文件夹' })).toBeVisible()
  await expect(nav.getByText('资料库', { exact: true })).toHaveCount(0)
})

test('hides standalone assets for the super account without changing authorization choices', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/shops')
  await expect(
    page.getByRole('columnheader', { name: '店铺名称' }),
  ).toBeVisible()
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await expect(
    page.getByRole('button', { name: '当前用户菜单' }),
  ).toContainText('管理员预览')
  await expect(nav.getByText('资料库', { exact: true })).toHaveCount(0)
  await page.screenshot({
    path: testInfo.outputPath('super-account-hidden-assets.png'),
    animations: 'disabled',
  })
  // Read the code-owned authorization catalog, not the filtered Sidebar.
  const options = await page.evaluate(async () => {
    const registryPath = '/src/app/modules/registry.ts'
    const { getModuleAccessOptions } = await import(registryPath)
    return getModuleAccessOptions()
  })
  expect(options).toContainEqual({ value: 'asset', label: '资料库' })
})

test('selects ordered assets for one run and resets the next run to empty', async ({
  page,
}) => {
  await page.goto('/#/devices')
  await page.getByRole('button', { name: '能力' }).first().click()
  const capabilityDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /设备能力 · 杭州-运营机-01/ }),
  })
  await capabilityDrawer.getByRole('button', { name: '运行' }).first().click()

  let runDialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /运行应用 · 商品发布/ }),
  })
  await expect(runDialog.getByText('未选择图片', { exact: true })).toBeVisible()
  await runDialog.getByRole('button', { name: '选择资料库图片' }).click()

  const selector = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: '选择资料库图片' }),
  })
  const checkboxes = selector.getByRole('checkbox')
  await checkboxes.nth(1).check()
  await checkboxes.nth(2).check()
  await selector.getByRole('button', { name: '确认选择' }).click()
  await expect(runDialog.getByText('已选择 2 张图片')).toBeVisible()
  await runDialog.getByRole('button', { name: '取消' }).click()

  await capabilityDrawer.getByRole('button', { name: '运行' }).first().click()
  runDialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: /运行应用 · 商品发布/ }),
  })
  await expect(runDialog.getByText('未选择图片', { exact: true })).toBeVisible()
})
