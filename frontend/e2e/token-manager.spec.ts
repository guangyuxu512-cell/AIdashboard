import { expect, test } from '@playwright/test'

test('standalone token manager creates an individually scoped token once', async ({ page }) => {
  const requests: unknown[] = []
  const permissions = [
    { id: 'GET /api/v1/tasks', module: 'tasks', name: 'List Tasks', team_scoped: true },
    { id: 'POST /api/v1/tasks', module: 'tasks', name: 'Create Task', team_scoped: true },
    { id: 'GET /api/v1/devices', module: 'devices', name: 'List Devices', team_scoped: false },
  ]
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: { user_id: 'test-user', display_name: '测试管理员' } }))
  await page.route('**/api/v1/access/me/teams', (route) => route.fulfill({ json: [{ team_id: 'test-team', team_name: '测试团队' }] }))
  await page.route('**/api/v1/api-tokens/permissions', (route) => route.fulfill({ json: permissions }))
  await page.route('**/api/v1/api-tokens', async (route) => {
    if (route.request().method() === 'POST') {
      requests.push(route.request().postDataJSON())
      await route.fulfill({ status: 201, json: { value: 'fixture-only-value', token: {} } })
    } else await route.fulfill({ json: [] })
  })

  await page.goto('/token-manager/')
  await expect(page.getByRole('heading', { name: '中控 Token 管理' })).toBeVisible()
  await page.getByRole('button', { name: '新建 Token' }).click()
  await page.getByPlaceholder('例如：AI 助手').fill('测试助手')
  await page.getByRole('button', { name: '全选读取' }).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('完整 Token 只显示这一次，请立即复制并保存。')).toBeVisible()
  expect(requests).toEqual([{
    name: '测试助手', permissions: ['GET /api/v1/tasks', 'GET /api/v1/devices'],
    team_ids: null, enabled: true, expires_at: null,
  }])
  await page.getByRole('button', { name: '已保存' }).click()
  await expect(page.getByText('完整 Token 只显示这一次，请立即复制并保存。')).not.toBeVisible()
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('fixture-only-value')
})
