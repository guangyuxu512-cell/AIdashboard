import { expect, test } from '@playwright/test'

test('product placeholders preserve navigation, tabs and history in all four themes', async ({
  page,
}, testInfo) => {
  const errors: string[] = []
  const businessRequests: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/'))
      businessRequests.push(request.url())
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/product-selection')
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await expect(nav.getByText('商品中心', { exact: true })).toBeVisible()
  await expect(nav.getByText('数据中心', { exact: true })).toBeVisible()
  await nav.getByText('商品中心', { exact: true }).click()
  await expect(
    page.getByText('候选池功能待接入', { exact: true }),
  ).toBeVisible()
  const tabs = page.locator('.n-tabs-tab')
  await expect(tabs).toHaveCount(2)
  for (const [id, label] of [
    ['graphite', '石墨浅色'],
    ['forest', '森林绿'],
    ['coral', '珊瑚红'],
    ['midnight', '午夜青'],
  ]) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label!, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id!)
    await tabs.getByText('候选池', { exact: true }).click()
    await expect(
      page.getByText('候选池功能待接入', { exact: true }),
    ).toBeVisible()
    await expect(page.locator('.n-tab-pane')).toHaveCount(1)
    await page.screenshot({
      path: testInfo.outputPath(`${id}-candidate-pool.png`),
      animations: 'disabled',
    })
    await tabs.getByText('采集任务', { exact: true }).click()
    await expect(page).toHaveURL(/tab=collection-tasks/)
    await expect(
      page.getByText('采集任务功能待接入', { exact: true }),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByText('采集任务功能待接入', { exact: true }),
    ).toBeVisible()
    if (!(await nav.getByText('选品库', { exact: true }).isVisible()))
      await nav.getByText('商品中心', { exact: true }).click()
    await nav.getByText('选品库', { exact: true }).click()
    await expect(page.locator('.n-tab-pane')).toHaveCount(1)
    await page.screenshot({
      path: testInfo.outputPath(`${id}-collection-tasks.png`),
      animations: 'disabled',
    })
    if (!(await nav.getByText('商品库', { exact: true }).isVisible()))
      await nav.getByText('商品中心', { exact: true }).click()
    await nav.getByText('商品库', { exact: true }).click()
    await expect(page).toHaveURL(/#\/products$/)
    await expect(
      page.getByText('商品库功能待接入', { exact: true }),
    ).toBeVisible()
    await expect(nav.locator('.n-menu-item-content--selected')).toHaveText(
      '商品库',
    )
    await page.reload()
    await expect(
      page.getByText('商品库功能待接入', { exact: true }),
    ).toBeVisible()
    if (!(await nav.getByText('商品库', { exact: true }).isVisible()))
      await nav.getByText('商品中心', { exact: true }).click()
    await nav.getByText('商品库', { exact: true }).click()
    await page.screenshot({
      path: testInfo.outputPath(`${id}-products.png`),
      animations: 'disabled',
    })
    await page.goBack()
    await expect(
      page.getByText('采集任务功能待接入', { exact: true }),
    ).toBeVisible()
    if (!(await nav.getByText('选品库', { exact: true }).isVisible()))
      await nav.getByText('商品中心', { exact: true }).click()
    await expect(nav.locator('.n-menu-item-content--selected')).toHaveText(
      '选品库',
    )
    await tabs.getByText('候选池', { exact: true }).click()
    await page.goBack()
    await expect(
      page.getByText('采集任务功能待接入', { exact: true }),
    ).toBeVisible()
    await page.goForward()
    await expect(
      page.getByText('候选池功能待接入', { exact: true }),
    ).toBeVisible()
  }
  for (const width of [960, 1920]) {
    await page.setViewportSize({ width, height: 800 })
    await expect(tabs.getByText('采集任务', { exact: true })).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  }
  expect(businessRequests).toEqual([])
  await nav.getByText('店铺中心', { exact: true }).click()
  await expect(
    page.getByRole('columnheader', { name: '店铺名称' }),
  ).toBeVisible()
  if (!(await nav.getByText('经营看板', { exact: true }).isVisible()))
    await nav.getByText('数据中心', { exact: true }).click()
  await nav.getByText('经营看板', { exact: true }).click()
  await expect(
    page.getByRole('columnheader', { name: '成交金额' }),
  ).toBeVisible()
  if (!(await nav.getByText('参数配置', { exact: true }).isVisible()))
    await nav.getByText('自动化中心', { exact: true }).click()
  await nav.getByText('参数配置', { exact: true }).click()
  await expect(
    page.getByRole('button', { name: '+ 新建配置', exact: true }),
  ).toBeVisible()
  expect(errors).toEqual([])
})
