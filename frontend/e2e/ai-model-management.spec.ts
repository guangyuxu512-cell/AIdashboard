import { expect, test } from '@playwright/test'

test.skip(
  process.env.PLAYWRIGHT_API_MODE === 'real',
  'Mock mode model management coverage',
)

test('manages the AI model catalog with the existing settings shell', async ({
  page,
}) => {
  const consoleErrors: string[] = []
  await page.setViewportSize({ width: 1366, height: 768 })
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await page.goto('/#/settings/ai-models')
  await expect(page.getByRole('heading', { name: 'AI 模型管理' })).toBeVisible()
  await expect(
    page
      .getByRole('navigation', { name: '系统设置' })
      .getByRole('button', { name: 'AI 模型管理' }),
  ).toHaveAttribute('aria-current', 'page')

  const initialRow = page.locator('tr').filter({ hasText: 'GPT Image 2' })
  await expect(initialRow).toContainText('gpt-image-2')
  await expect(initialRow).toContainText('ToAPIs')
  await expect(initialRow).toContainText('普通生图 / 风格复刻')
  await expect(initialRow).toContainText('默认')
  await expect(initialRow).toContainText('已启用')
  await expect(initialRow.getByRole('button', { name: '停用' })).toBeDisabled()

  await page.getByRole('button', { name: '新增模型' }).click()
  await expect(page.locator('.app-dialog__title')).toHaveText('新增模型')
  await page.getByLabel('模型名称').fill('Next Image Model')
  await page.getByLabel('Model Code').fill('next-image-model')
  await page.getByRole('button', { name: '保存', exact: true }).click()

  let newRow = page.locator('tr').filter({ hasText: 'Next Image Model' })
  await expect(newRow).toContainText('next-image-model')
  await newRow.getByRole('button', { name: '编辑' }).click()
  await expect(page.getByLabel('Model Code')).toBeDisabled()
  await expect(
    page.getByLabel('Provider').locator('.n-base-selection'),
  ).toHaveClass(/n-base-selection--disabled/)
  await page.getByLabel('模型名称').fill('Updated Image Model')
  await page.getByRole('button', { name: '保存', exact: true }).click()

  newRow = page.locator('tr').filter({ hasText: 'Updated Image Model' })
  await expect(newRow).toBeVisible()
  await newRow.getByRole('button', { name: '设为默认' }).click()
  await expect(newRow).toContainText('默认')

  await initialRow.getByRole('button', { name: '停用' }).click()
  await expect(initialRow).toContainText('已停用')

  await page.getByLabel('模型状态').click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: '已停用' })
    .click()
  await expect(initialRow).toBeVisible()
  await expect(newRow).toHaveCount(0)
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true)

  expect(consoleErrors).toEqual([])
})

test('hides model management from ordinary members and guards the route', async ({
  page,
}) => {
  await page.goto('/#/settings/notifications')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await page.getByLabel('内部登录账号').fill('operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/#\/shops$/)
  await page.goto('/#/settings/notifications')
  await expect(
    page
      .getByRole('navigation', { name: '系统设置' })
      .getByRole('button', { name: 'AI 模型管理' }),
  ).toHaveCount(0)

  await page.goto('/#/settings/ai-models')
  await expect(page).toHaveURL(/#\/permission-denied$/)
})
