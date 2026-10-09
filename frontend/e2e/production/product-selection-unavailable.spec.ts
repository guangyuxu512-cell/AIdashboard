import { expect, test } from '@playwright/test'

test('Real keeps unavailable state without Mock fallback and retains route permission guard', async ({
  page,
}, info) => {
  let allowed = true
  const unexpected: string[] = []
  const runtimeErrors: string[] = []
  const mockModules: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('selection-mock-handlers'))
      mockModules.push(request.url())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  // Match the API root, not Vite's /src/shared/api/*.ts modules.
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    const response =
      path === '/api/v1/auth/me'
        ? { user_id: 'test-person', display_name: '隔离前端验证' }
        : path === '/api/v1/access/me/teams'
          ? [
              {
                membership_id: 'test-member',
                team_id: 'test-team',
                team_name: '测试团队',
                team_enabled: true,
                membership_enabled: true,
                role_code: 'member',
                data_scope: 'team',
              },
            ]
          : path === '/api/v1/access-management/me/module-access'
            ? {
                module_codes: allowed
                  ? ['product-selection', 'product-library']
                  : ['product-library'],
                is_super_account: false,
                is_access_administrator: false,
              }
            : null
    if (!response) {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: response })
  })
  await page.goto('/#/product-selection')
  await expect.poll(() => runtimeErrors).toEqual([])
  await expect(
    page.getByText('选品能力尚未接入', { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('演示商品 1', { exact: true })).toHaveCount(0)
  await expect(page.getByText('演示数据', { exact: true })).toHaveCount(0)
  await page
    .getByRole('navigation', { name: '选品库切换' })
    .getByRole('button', { name: '选品策略', exact: true })
    .click()
  await expect(
    page.getByText('选品能力尚未接入', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '新建策略', exact: true }),
  ).toHaveCount(0)
  await expect(page.getByText(/Mock 示例区间/)).toHaveCount(0)
  expect(mockModules).toEqual([])
  await page.screenshot({
    path: info.outputPath('real-unavailable.png'),
    animations: 'disabled',
  })
  expect(unexpected).toEqual([])
  allowed = false
  await page.reload()
  await expect(page).toHaveURL(/permission-denied/)
  expect(unexpected).toEqual([])
})
