import { expect, test, type Page } from '@playwright/test'

async function expectRoleCount(
  page: Page,
  label: '商品素材' | '复刻参考' | 'AI成品',
  count: number,
): Promise<void> {
  const roleButton = page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: `${label} ${count}` })
  await expect(roleButton).toBeVisible()
  await roleButton.click()
  await expect(page.getByRole('button', { name: /^查看素材 / })).toHaveCount(
    count,
  )
}

test('manages the isolated AI assets visual mock', async ({ page }) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/assets?visualMock=1')

  const moduleNavigation = page.getByRole('navigation', {
    name: 'AI 功能入口',
  })
  await expect(
    moduleNavigation.getByRole('button', { name: '素材库' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    page.getByRole('button', { name: '选择产品 手机支架' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expectRoleCount(page, '商品素材', 5)
  await expectRoleCount(page, '复刻参考', 3)
  await expectRoleCount(page, 'AI成品', 6)
  await expect(page.getByRole('button', { name: '上传素材' })).toBeDisabled()

  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: '商品素材 5' })
    .click()

  const productEnabled = page.getByRole('switch', { name: '产品启用' })
  const normalEnabled = page.getByRole('switch', { name: '普通生图' })
  const styleEnabled = page.getByRole('switch', { name: '风格复刻' })
  await productEnabled.click()
  await expect(normalEnabled).toBeDisabled()
  await expect(styleEnabled).toBeDisabled()
  await page.getByRole('switch', { name: '手机支架启用状态' }).click()
  await expect(normalEnabled).toBeEnabled()
  await expect(styleEnabled).toBeEnabled()
  await normalEnabled.click()
  await styleEnabled.click()

  await page.locator('.product-material-settings .n-select').click()
  await page.getByText('生活场景组', { exact: true }).click()
  await expect(
    page.locator('.product-material-settings .n-select'),
  ).toContainText('生活场景组')

  await page
    .getByRole('button', { name: /^查看素材 / })
    .first()
    .click()
  const inspector = page.getByRole('region', { name: '素材详情' })
  await expect(inspector).toBeVisible()
  await expect(inspector.getByText('素材导入', { exact: true })).toBeVisible()
  await inspector.getByRole('button', { name: '返回产品设置' }).click()
  await expect(page.getByRole('region', { name: '产品设置' })).toBeVisible()

  await page.getByRole('button', { name: '新建产品' }).click()
  const createDialog = page.getByRole('dialog').filter({ hasText: '新建产品' })
  await createDialog.getByPlaceholder('请输入产品名称').fill('桌面灯')
  await createDialog.getByPlaceholder('请输入 SKU').fill('ZM-D-001')
  await createDialog.getByRole('button', { name: '创建' }).click()
  await expect(
    page.getByRole('button', { name: '选择产品 桌面灯' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expectRoleCount(page, '商品素材', 0)

  await page.locator('input[type="file"]').setInputFiles({
    name: '桌面灯-正面.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      'base64',
    ),
  })
  await expect(page.getByText('上传成功', { exact: true })).toBeVisible()
  await expectRoleCount(page, '商品素材', 1)
  await page.getByRole('button', { name: '查看素材 桌面灯-正面.png' }).click()
  await page
    .getByRole('region', { name: '素材详情' })
    .getByRole('button', { name: '删除' })
    .click()
  const deleteDialog = page.getByRole('dialog').filter({ hasText: '删除素材' })
  await deleteDialog.getByRole('button', { name: '删除' }).click()
  await expect(
    page.getByRole('button', { name: '查看素材 桌面灯-正面.png' }),
  ).toHaveCount(0)
  await expect(
    page
      .getByRole('navigation', { name: '素材角色' })
      .getByRole('button', { name: '商品素材 0' }),
  ).toBeVisible()

  await page.getByPlaceholder('搜索素材').fill('BWB-500')
  await expect(
    page.getByRole('button', { name: '选择产品 保温杯' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '选择产品 手机支架' }),
  ).toHaveCount(0)
  await page.getByPlaceholder('搜索素材').clear()

  await page.getByRole('button', { name: /^筛选：/ }).click()
  await page.getByText('已停用产品', { exact: true }).click()
  await expect(
    page.getByRole('button', { name: '选择产品 戒指' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '选择产品 保温杯' }),
  ).toHaveCount(0)

  const layout = await page.evaluate(() => {
    const main = document.querySelector<HTMLElement>('.app-shell__content')
    return {
      documentHorizontalOverflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      bodyHorizontalOverflow:
        document.body.scrollWidth > document.body.clientWidth,
      bodyOverflow: getComputedStyle(document.body).overflow,
      mainHorizontalOverflow: main ? main.scrollWidth > main.clientWidth : true,
    }
  })
  expect(layout).toEqual({
    documentHorizontalOverflow: false,
    bodyHorizontalOverflow: false,
    bodyOverflow: 'hidden',
    mainHorizontalOverflow: false,
  })
  expect(runtimeErrors).toEqual([])
})

test('keeps normal and non-exact query routes free of visual fixtures', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/assets')
  await expect(page.getByText('暂无素材', { exact: true })).toBeVisible()
  await expect(page.getByText('手机支架', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '上传素材' })).toBeDisabled()

  await page.goto('/#/ai-workbench/assets?visualMock=true')
  await expect(page.getByText('暂无素材', { exact: true })).toBeVisible()
  await expect(page.getByText('手机支架', { exact: true })).toHaveCount(0)
})

test('renders the AI assets visual mock in light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/ai-workbench/assets?visualMock=1')
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(
    page.getByRole('button', { name: '选择产品 手机支架' }),
  ).toBeVisible()

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('浅色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByRole('region', { name: '产品设置' })).toBeVisible()
})
