import { expect, test } from '@playwright/test'

test('product navigation preserves framed query history, refresh, fallback and library placeholder', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#/product-selection?tab=collection-tasks&context=preserved')
  const bar = page.getByRole('navigation', { name: '选品库切换', exact: true })
  await expect(bar).toHaveAttribute('data-appearance', 'framed')
  await expect(
    page.getByText('采集任务功能待接入', { exact: true }),
  ).toBeVisible()
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
    bar.getByRole('button', { name: '采集任务', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await page.goForward()
  await expect(
    bar.getByRole('button', { name: '选品策略', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await bar.getByRole('button', { name: '候选池', exact: true }).click()
  await expect(page).toHaveURL(/product-selection\?context=preserved$/)
  await expect(
    page.getByRole('columnheader', { name: '商品标题', exact: true }),
  ).toBeVisible()
  await page.goto('/#/product-selection?tab=unknown')
  await expect(
    bar.getByRole('button', { name: '候选池', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await page.goto('/#/products')
  await expect(
    page.getByText('商品库功能待接入', { exact: true }),
  ).toBeVisible()
  const nav = page.getByRole('navigation', { name: '主导航', exact: true })
  await nav.getByText('商品中心', { exact: true }).click()
  await expect(nav.locator('.n-menu-item-content--selected')).toHaveText(
    '商品库',
  )
  await nav.getByText('选品库', { exact: true }).click()
  await expect(nav.locator('.n-menu-item-content--selected')).toHaveText(
    '选品库',
  )
  for (const width of [960, 1920]) {
    await page.setViewportSize({ width, height: 800 })
    for (const label of ['候选池', '采集任务', '选品策略'])
      await expect(
        bar.getByRole('button', { name: label, exact: true }),
      ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  }
  await nav.getByText('店铺中心', { exact: true }).click()
  await expect(
    page.getByRole('columnheader', { name: '店铺名称' }),
  ).toBeVisible()
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

test('product switch uses the same shared framed styling as AI navigation in all themes', async ({
  page,
}) => {
  const apiAttempts: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/'))
      apiAttempts.push(request.method())
  })
  // UI comparison uses the existing isolated fixture, never Real AI APIs.
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (
      url.origin === new URL(test.info().project.use.baseURL!).origin &&
      !url.pathname.startsWith('/api/')
    )
      await route.continue()
    else await route.abort()
  })
  const style = async (label: string) =>
    page
      .getByRole('navigation', { name: label, exact: true })
      .evaluate((element) => {
        const css = getComputedStyle(element)
        const active = getComputedStyle(
          element.querySelector('[aria-pressed="true"]')!,
        )
        const normal = getComputedStyle(
          element.querySelector('[aria-pressed="false"]')!,
        )
        return [
          css.padding,
          css.gap,
          css.border,
          css.borderRadius,
          css.backgroundColor,
          active.backgroundColor,
          active.color,
          active.borderColor,
          active.height,
          normal.backgroundColor,
          normal.color,
          normal.borderColor,
          normal.height,
        ]
      })
  for (const label of ['石墨浅色', '森林绿', '珊瑚红', '午夜青']) {
    await page.goto('/#/ai-workbench/generate?visualMock=1')
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('.n-dropdown')).toBeHidden()
    // Finish theme transitions before comparing computed button colours.
    await page
      .getByRole('navigation', { name: 'AI 功能入口', exact: true })
      .screenshot({ animations: 'disabled' })
    const ai = await style('AI 功能入口')
    await page.goto('/#/product-selection')
    expect(await style('选品库切换')).toEqual(ai)
  }
  expect(apiAttempts).toEqual([])
})
