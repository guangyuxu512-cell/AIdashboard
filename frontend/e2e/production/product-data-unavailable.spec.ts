import { expect, test } from '@playwright/test'

test('Real refuses guessed product IO and Mock fallback and still enforces Shop authorization', async ({
  page,
}, info) => {
  let allowed = true
  const unexpected: string[] = [],
    mockModules: string[] = [],
    errors: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/product-data-mock'))
      mockModules.push(request.url())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    const data =
      path === '/api/v1/auth/me'
        ? { user_id: 'product-real-test', display_name: '隔离前端验收' }
        : path === '/api/v1/access/me/teams'
          ? [
              {
                membership_id: 'member',
                team_id: 'team',
                team_name: '测试团队',
                team_enabled: true,
                membership_enabled: true,
                role_code: 'member',
                data_scope: 'team',
              },
            ]
          : path === '/api/v1/access-management/me/module-access'
            ? {
                module_codes: allowed ? ['shop'] : ['device'],
                is_super_account: false,
                is_access_administrator: false,
              }
            : path === '/api/v1/shops'
              ? { items: [], total: 0, page: 1, page_size: 100 }
              : null
    if (!data) {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: data })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/product-data?productDataPreview=query-error')
  await expect(
    page.getByText('商品数据接口尚未接入', { exact: true }).first(),
  ).toBeVisible()
  for (const name of ['查询', '重置', '分组管理', '批量设置分组'])
    await expect(page.getByRole('button', { name, exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(
    page.getByText('商品数据接口尚未接入', { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByText('演示数据', { exact: true })).toHaveCount(0)
  await expect(
    page.getByText('所选范围暂无商品数据', { exact: true }),
  ).toHaveCount(0)
  await expect(page.locator('.pagination-bar')).toHaveCount(0)
  expect(unexpected).toEqual([])
  expect(mockModules).toEqual([])
  expect(errors).toEqual([])
  await page.screenshot({
    path: info.outputPath('product-data-real-unavailable.png'),
    animations: 'disabled',
  })
  allowed = false
  await page.reload()
  await expect(page).toHaveURL(/permission-denied/)
  expect(unexpected).toEqual([])
})
