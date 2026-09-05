import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode access coverage')

async function logout(page: import('@playwright/test').Page): Promise<void> {
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await expect(page).toHaveURL(/#\/login$/)
}

test('shows operation logs to an access administrator and rejects a member', async ({
  page,
}) => {
  await page.goto('/#/settings/audit-logs')
  await expect(page.getByRole('heading', { name: '操作日志' })).toBeVisible()
  await expect(page.getByText('暂无操作日志', { exact: true })).toBeVisible()
  await expect(
    page
      .getByRole('navigation', { name: '系统设置主导航' })
      .getByText('系统设置', { exact: true }),
  ).toBeVisible()
  await expect(
    page
      .getByRole('navigation', { name: '系统设置' })
      .getByRole('button', { name: '用户与权限' }),
  ).toBeVisible()

  await logout(page)
  await page.goto('/#/settings/audit-logs')
  await page.getByLabel('内部登录账号').fill('operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/permission-denied$/)
})
