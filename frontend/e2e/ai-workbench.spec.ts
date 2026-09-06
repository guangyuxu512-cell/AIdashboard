import { expect, test, type Page } from '@playwright/test'

const removedCopy = [
  '组合商品素材、生成模式与输出类型，创建电商视觉内容。',
  '添加商品图、参考图或品牌素材。',
  '选择适合当前商品的创作方式。',
  '按投放场景组织生成内容。',
  '补充画面要求，或引用模板快速开始。',
  '添加素材并完成创作设置后，在此查看预览。',
  '统一管理 AI 创作使用的商品图片、参考图片与品牌素材。',
  '沉淀可复用的创作模板，统一组织画面要求与输出结构。',
]

async function expectShellBoundaries(page: Page): Promise<void> {
  const layout = await page.evaluate(() => {
    const main = document.querySelector<HTMLElement>('.app-shell__content')!
    return {
      bodyOverflow: getComputedStyle(document.body).overflow,
      documentHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
      mainHorizontalOverflow: main.scrollWidth > main.clientWidth,
      mainVerticalOverflow: main.scrollHeight > main.clientHeight,
    }
  })

  expect(layout).toEqual({
    bodyOverflow: 'hidden',
    documentHorizontalOverflow: false,
    bodyHorizontalOverflow: false,
    mainHorizontalOverflow: false,
    mainVerticalOverflow: false,
  })
}

async function expectNoExplanatoryCopy(page: Page): Promise<void> {
  await expect(page.locator('.ai-module-shell h1')).toHaveCount(0)
  await expect(page.locator('.ai-module-shell .page-header')).toHaveCount(0)
  await expect(page.getByText('操作区', { exact: true })).toHaveCount(0)
  await expect(page.getByText('工作区', { exact: true })).toHaveCount(0)
  for (const copy of removedCopy) {
    await expect(page.getByText(copy, { exact: true })).toHaveCount(0)
  }
}

test('keeps the four AI pages route-backed, compact and explanation-free', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/generate')

  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(moduleNavigation).toBeVisible()
  await expect(moduleNavigation.getByRole('button')).toHaveCount(4)
  await expect(
    moduleNavigation.getByRole('button', { name: 'AI生图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    moduleNavigation.getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'false')
  await expect(
    moduleNavigation.getByRole('button', { name: '模板库' }),
  ).toHaveAttribute('aria-pressed', 'false')
  await expect(
    moduleNavigation.getByRole('button', { name: '生成记录' }),
  ).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByText('平台切换', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('region', { name: '生成工作方式' })).toBeVisible()
  await expect(page.getByRole('region', { name: '即时生成配置' })).toBeVisible()
  await expect(page.getByRole('region', { name: '即时生成结果' })).toBeVisible()
  await expect(
    page
      .getByRole('navigation', { name: '生成工作方式' })
      .getByRole('button', { name: '即时生成' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    page
      .getByRole('navigation', { name: '生成模式' })
      .getByRole('button', { name: '普通生图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()

  const columns = await page.evaluate(() => {
    const operation = document
      .querySelector('[aria-label="即时生成配置"]')
      ?.getBoundingClientRect()
    const workspace = document
      .querySelector('[aria-label="即时生成结果"]')
      ?.getBoundingClientRect()
    const configScroller = document.querySelector<HTMLElement>(
      '.instant-generation-pane__scroll',
    )!
    return {
      operationLeft: operation?.left,
      workspaceLeft: workspace?.left,
      configUsesLocalScroll:
        configScroller.scrollHeight > configScroller.clientHeight,
    }
  })
  expect(columns.operationLeft).toBeLessThan(columns.workspaceLeft ?? 0)
  expect(columns.configUsesLocalScroll).toBe(true)

  await expectNoExplanatoryCopy(page)
  await expectShellBoundaries(page)

  await moduleNavigation.getByRole('button', { name: '素材库' }).click()
  await expect(page).toHaveURL(/#\/ai-workbench\/assets$/)
  await expect(page.getByPlaceholder('搜索素材')).toBeVisible()
  await expect(page.getByRole('button', { name: '上传素材' })).toBeDisabled()
  await expect(page.getByText('暂无素材', { exact: true })).toBeVisible()
  await expectNoExplanatoryCopy(page)
  await expectShellBoundaries(page)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/templates$/)
  await expect(page.getByPlaceholder('搜索模板')).toBeVisible()
  await expect(page.getByRole('button', { name: '新建模板组' })).toBeDisabled()
  await expect(page.getByText('暂无模板', { exact: true })).toBeVisible()
  await expectNoExplanatoryCopy(page)
  await expectShellBoundaries(page)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/records$/)
  await expect(page.getByText('暂无生成记录', { exact: true })).toBeVisible()
  await expectNoExplanatoryCopy(page)
  await expectShellBoundaries(page)
  expect(runtimeErrors).toEqual([])
})

test('renders the AI generation workbench in light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/generate')

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()
  await expectShellBoundaries(page)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()
  await expectShellBoundaries(page)
})
