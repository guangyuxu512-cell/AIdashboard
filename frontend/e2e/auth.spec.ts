import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode auth coverage')

test('guards business routes, logs in, restores and logs out without changing theme', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await expect(page).toHaveURL(/#\/login/)
  await expect(
    page.getByRole('heading', { name: '思余AI中控台' }),
  ).toBeVisible()
  await expect(page.locator('.app-shell')).toHaveCount(0)

  await page.goto('/#/devices')
  await expect(page).toHaveURL(/#\/login\?redirect=\/devices/)

  await page.getByRole('button', { name: '切换主题' }).click()
  await page.getByText('深色', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByLabel('内部登录账号').fill('operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.locator('.app-shell')).toBeVisible()
  await expect(
    page.getByRole('button', { name: '当前用户菜单' }),
  ).toContainText('测试人员')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('.app-shell')).toBeVisible()

  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await expect(page).toHaveURL(/#\/login$/)
})

test('requires first team selection and supports later team switching', async ({
  page,
}) => {
  await page.goto('/#/shops')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()

  await page.getByLabel('内部登录账号').fill('multi-operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByText('选择当前团队', { exact: true })).toBeVisible()

  await page.locator('.login-card .n-base-selection').click()
  await page.getByText('运营团队', { exact: true }).click()
  await page.getByRole('button', { name: '进入中控台' }).click()
  await expect(page).toHaveURL(/#\/shops$/)

  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await expect(page.getByText('当前团队：运营团队')).toBeVisible()
  await page.getByText('切换至 默认团队', { exact: true }).click()
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await expect(page.getByText('当前团队：默认团队')).toBeVisible()
})
