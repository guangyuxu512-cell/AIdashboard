import { expect, test, type Locator } from '@playwright/test'

const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const

const selectionLabels = ['候选池', '采集任务', '选品策略'] as const

async function expectSelection(
  bar: Locator,
  name: (typeof selectionLabels)[number],
) {
  await expect(bar).toHaveAttribute('data-appearance', 'framed')
  await expect(bar.getByRole('button')).toHaveCount(selectionLabels.length)
  for (const label of selectionLabels) {
    await expect(
      bar.getByRole('button', { name: label, exact: true }),
    ).toHaveAttribute('aria-pressed', String(label === name))
  }
}

async function switchStyles(bar: Locator) {
  return bar.evaluate((element) => {
    const container = getComputedStyle(element)
    const active = getComputedStyle(
      element.querySelector('[aria-pressed="true"]')!,
    )
    const normal = getComputedStyle(
      element.querySelector('[aria-pressed="false"]')!,
    )
    return {
      padding: container.padding,
      gap: container.gap,
      border: container.border,
      radius: container.borderRadius,
      background: container.backgroundColor,
      active: [
        active.backgroundColor,
        active.color,
        active.borderColor,
        active.height,
      ],
      normal: [
        normal.backgroundColor,
        normal.color,
        normal.borderColor,
        normal.height,
      ],
    }
  })
}

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
  const tabs = page.getByRole('navigation', { name: '选品库切换', exact: true })
  await expectSelection(tabs, '候选池')
  for (const [id, label] of themes) {
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label!, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id!)
    await tabs.getByRole('button', { name: '候选池', exact: true }).click()
    await expect(
      page.getByText('候选池功能待接入', { exact: true }),
    ).toBeVisible()
    await expectSelection(tabs, '候选池')
    await page.screenshot({
      path: testInfo.outputPath(`${id}-candidate-pool.png`),
      animations: 'disabled',
    })
    await tabs.getByRole('button', { name: '采集任务', exact: true }).click()
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
    await expectSelection(tabs, '采集任务')
    await page.screenshot({
      path: testInfo.outputPath(`${id}-collection-tasks.png`),
      animations: 'disabled',
    })
    await tabs.getByRole('button', { name: '选品策略', exact: true }).click()
    await expect(page).toHaveURL(/tab=selection-strategy/)
    await expect(
      page.getByText('选品策略待接入', { exact: true }),
    ).toBeVisible()
    await expectSelection(tabs, '选品策略')
    await page.reload()
    await expectSelection(tabs, '选品策略')
    await expect(
      page.getByText('选品策略待接入', { exact: true }),
    ).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath(`${id}-selection-strategy.png`),
      animations: 'disabled',
    })
    await page.goBack()
    await expectSelection(tabs, '采集任务')
    await page.goForward()
    await expectSelection(tabs, '选品策略')
    await tabs.getByRole('button', { name: '采集任务', exact: true }).click()
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
    await tabs.getByRole('button', { name: '候选池', exact: true }).click()
    await page.goBack()
    await expect(
      page.getByText('采集任务功能待接入', { exact: true }),
    ).toBeVisible()
    await expectSelection(tabs, '采集任务')
    await page.goForward()
    await expect(
      page.getByText('候选池功能待接入', { exact: true }),
    ).toBeVisible()
    await expectSelection(tabs, '候选池')
  }
  await page.goto('/#/product-selection?tab=collection-tasks&context=preserved')
  await expectSelection(tabs, '采集任务')
  await page.reload()
  await expectSelection(tabs, '采集任务')
  await tabs.getByRole('button', { name: '候选池', exact: true }).click()
  await expect(page).toHaveURL(/product-selection\?context=preserved$/)
  await expectSelection(tabs, '候选池')
  await page.goto(
    '/#/product-selection?tab=selection-strategy&context=preserved',
  )
  await expectSelection(tabs, '选品策略')
  await expect(page.getByText('选品策略待接入', { exact: true })).toBeVisible()
  await page.reload()
  await expectSelection(tabs, '选品策略')
  await tabs.getByRole('button', { name: '候选池', exact: true }).click()
  await expect(page).toHaveURL(/product-selection\?context=preserved$/)
  await page.goto('/#/product-selection?tab=unknown')
  await expectSelection(tabs, '候选池')
  for (const width of [960, 1920]) {
    await page.setViewportSize({ width, height: 800 })
    for (const name of selectionLabels)
      await expect(
        tabs.getByRole('button', { name, exact: true }),
      ).toBeVisible()
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

test('product switch matches the existing AI framed navigation in all four themes', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const [id, label] of themes) {
    await page.goto('/#/ai-workbench/generate?visualMock=1')
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id)
    const aiBar = page.getByRole('navigation', {
      name: 'AI 功能入口',
      exact: true,
    })
    await expect(aiBar).toHaveAttribute('data-appearance', 'framed')
    await expect(aiBar.getByRole('button')).toHaveCount(4)
    // Keep screenshots and computed-style comparisons out of animation middle frames.
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await aiBar.screenshot({
      path: testInfo.outputPath(`${id}-ai-top-switch.png`),
      animations: 'disabled',
    })
    const aiStyles = await switchStyles(aiBar)
    await page.screenshot({
      path: testInfo.outputPath(`${id}-ai-reference.png`),
      animations: 'disabled',
    })

    await page.goto('/#/product-selection')
    const productBar = page.getByRole('navigation', {
      name: '选品库切换',
      exact: true,
    })
    await expectSelection(productBar, '候选池')
    await expect(page.locator('html')).toHaveAttribute('data-theme-preset', id)
    await productBar.screenshot({
      path: testInfo.outputPath(`${id}-product-switch.png`),
      animations: 'disabled',
    })
    expect(await switchStyles(productBar)).toEqual(aiStyles)
  }
})
