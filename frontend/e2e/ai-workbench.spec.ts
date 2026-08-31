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

async function expectCompactAiLayout(page: Page): Promise<void> {
  const layout = await page.evaluate(() => {
    const nestedScrollers = Array.from(
      document.querySelectorAll<HTMLElement>('.ai-module-shell *'),
    ).filter((element) => {
      const style = getComputedStyle(element)
      return (
        ['auto', 'scroll'].includes(style.overflowY) &&
        element.scrollHeight > element.clientHeight + 1
      )
    })

    return {
      bodyOverflow: getComputedStyle(document.body).overflow,
      mainOverflowY: getComputedStyle(
        document.querySelector('.app-shell__content') as HTMLElement,
      ).overflowY,
      nestedScrollerCount: nestedScrollers.length,
      documentHasHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHasHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
    }
  })

  expect(layout.bodyOverflow).toBe('hidden')
  expect(layout.mainOverflowY).toBe('auto')
  expect(layout.nestedScrollerCount).toBe(0)
  expect(layout.documentHasHorizontalOverflow).toBe(false)
  expect(layout.bodyHasHorizontalOverflow).toBe(false)
}

async function expectNoExplanatoryCopy(page: Page): Promise<void> {
  await expect(page.locator('.ai-module-shell h1')).toHaveCount(0)
  await expect(page.locator('.ai-module-shell .page-header')).toHaveCount(0)
  await expect(page.getByText('操作区', { exact: true })).toHaveCount(0)
  await expect(page.getByText('工作区', { exact: true })).toHaveCount(0)
  await expect(page.getByText('预览', { exact: true })).toHaveCount(0)

  for (const copy of removedCopy) {
    await expect(page.getByText(copy, { exact: true })).toHaveCount(0)
  }
}

test('keeps the three AI pages route-backed, compact and explanation-free', async ({
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
  await expect(moduleNavigation.getByRole('button')).toHaveCount(3)
  await expect(
    moduleNavigation.getByRole('button', { name: 'AI生图' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    moduleNavigation.getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'false')
  await expect(
    moduleNavigation.getByRole('button', { name: '模板库' }),
  ).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByText('平台切换', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('region', { name: '生成设置' })).toBeVisible()
  await expect(
    page.getByRole('region', { name: '生成结果', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('素材', { exact: true })).toBeVisible()
  await expect(page.getByText('生成模式', { exact: true })).toBeVisible()
  await expect(page.getByText('输出类型', { exact: true })).toBeVisible()
  await expect(page.getByText('提示词 / 模板', { exact: true })).toBeVisible()
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()

  const columns = await page.evaluate(() => {
    const operation = document
      .querySelector('[aria-label="生成设置"]')
      ?.getBoundingClientRect()
    const workspace = document
      .querySelector('[aria-label="生成结果"]')
      ?.getBoundingClientRect()
    return { operationLeft: operation?.left, workspaceLeft: workspace?.left }
  })
  expect(columns.operationLeft).toBeLessThan(columns.workspaceLeft ?? 0)

  await expectNoExplanatoryCopy(page)
  await expectCompactAiLayout(page)

  await moduleNavigation.getByRole('button', { name: '素材库' }).click()
  await expect(page).toHaveURL(/#\/ai-workbench\/assets$/)
  await expect(
    moduleNavigation.getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByPlaceholder('搜索素材')).toBeVisible()
  await expect(page.getByRole('button', { name: '筛选' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传素材' })).toBeVisible()
  await expect(page.getByText('暂无素材', { exact: true })).toBeVisible()
  await page.reload()
  await expect(
    page
      .getByRole('navigation', { name: 'AI 功能入口' })
      .getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expectNoExplanatoryCopy(page)
  await expectCompactAiLayout(page)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/templates$/)
  await expect(page.getByPlaceholder('搜索模板')).toBeVisible()
  await page.getByLabel('生成模式').click()
  await expect(page.locator('.n-base-select-menu:visible')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '新建模板组' })).toBeDisabled()
  await expect(page.getByText('暂无模板', { exact: true })).toBeVisible()
  await page.reload()
  await expect(
    page
      .getByRole('navigation', { name: 'AI 功能入口' })
      .getByRole('button', { name: '模板库' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expectNoExplanatoryCopy(page)
  await expectCompactAiLayout(page)
  expect(runtimeErrors).toEqual([])
})

test('renders the compact AI workbench in light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/generate')

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()
  await expectCompactAiLayout(page)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByText('暂无生成结果', { exact: true })).toBeVisible()
  await expectCompactAiLayout(page)
})
