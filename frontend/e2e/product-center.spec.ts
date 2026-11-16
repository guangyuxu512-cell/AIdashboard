import { expect, test } from '@playwright/test'

test('product navigation preserves framed query history, refresh, fallback and product workspaces', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#/product-selection?tab=collection-tasks&context=preserved')
  const bar = page.getByRole('navigation', { name: '选品库切换', exact: true })
  await expect(bar).toHaveAttribute('data-appearance', 'framed')
  await expect(
    bar.getByRole('button', { name: '采集任务', exact: true }),
  ).toHaveCount(0)
  await expect(
    bar.getByRole('button', { name: '候选池', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await bar.getByRole('button', { name: '选品策略', exact: true }).click()
  await expect(page).toHaveURL(/tab=selection-strategy/)
  await expect(
    page.getByRole('button', { name: '新建策略', exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    bar.getByRole('button', { name: '选品策略', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await page.goBack()
  await expect(
    bar.getByRole('button', { name: '候选池', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await page.goForward()
  await expect(
    bar.getByRole('button', { name: '选品策略', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await bar.getByRole('button', { name: '候选池', exact: true }).click()
  await expect(page).toHaveURL(/product-selection\?context=preserved$/)
  await expect(
    page.getByRole('columnheader', { name: '商品信息', exact: true }),
  ).toBeVisible()
  await page.goto('/#/product-selection?tab=unknown')
  await expect(
    bar.getByRole('button', { name: '候选池', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await nav.getByText('商品中心', { exact: true }).click()
  await expect(nav.getByText('商品库', { exact: true })).toHaveCount(0)
  await nav.getByText('选品库', { exact: true }).click()
  await expect(nav.locator('.n-menu-item-content--selected')).toHaveText(
    '选品库',
  )
  for (const width of [960, 1920]) {
    await page.setViewportSize({ width, height: 800 })
    for (const label of ['候选池', '选品策略'])
      await expect(
        bar.getByRole('button', { name: label, exact: true }),
      ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  }
  await expect(nav.getByText('店铺中心', { exact: true })).toHaveCount(0)
  await nav.getByText('数据中心', { exact: true }).click()
  await nav.getByText('经营看板', { exact: true }).click()
  await expect(
    page.getByRole('columnheader', { name: '成交金额' }),
  ).toBeVisible()
  await nav.getByText('自动化中心', { exact: true }).click()
  await nav.getByText('参数配置', { exact: true }).click()
  await expect(
    page.getByRole('button', { name: '+ 新建配置', exact: true }),
  ).toBeVisible()
  expect(errors).toEqual([])
})
