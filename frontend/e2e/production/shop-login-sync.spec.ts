import { expect, test, type Page } from '@playwright/test'

const shopId = 'e2a01000-0000-4000-8000-000000000001'
const teamId = 'e2a01000-0000-4000-8000-000000000002'
const personId = 'shop-login-contract-person'
const timestamp = '2026-10-11T09:00:00Z'

async function prepare(
  page: Page,
  superAccount: boolean,
  pendingCapture = false,
) {
  const unexpected: string[] = []
  const writes: string[] = []
  let version = 1
  let status = 'valid'
  let healthFailure = 'unknown'
  await page.exposeFunction('finishSyncContract', () => ++version)
  await page.addInitScript(
    ({ teamId, personId, shopId, timestamp, pendingCapture }) => {
      localStorage.setItem(`control-center.active-team.${personId}`, teamId)
      const calls: string[] = []
      let retained = false
      let finishFocus: (() => void) | undefined
      Object.assign(window, {
        syncContractCalls: calls,
        finishFocusContract() {
          finishFocus?.()
        },
        desktop: {
          appearance: { setTitleBarTheme() {} },
          managementLogin: {
            ...(pendingCapture ? { correlationSupported: true as const } : {}),
            async focusShop() {
              calls.push('focus')
              if (retained && pendingCapture)
                await new Promise<void>((resolve) => {
                  finishFocus = resolve
                })
              return retained
            },
            async open() {
              calls.push('open')
              if (pendingCapture) retained = true
              return { attemptId: 'contract-attempt' }
            },
            async getStatus() {
              calls.push('status')
              return {
                attemptId: 'contract-attempt',
                status: pendingCapture ? 'opened' : 'identified',
                message: pendingCapture ? '等待人工登录' : '已识别目标店铺',
              }
            },
            async refresh() {
              calls.push('refresh')
              const sessionVersion = await (
                window as typeof window & {
                  finishSyncContract: () => Promise<number>
                }
              ).finishSyncContract()
              retained = true
              return {
                shopId,
                status: 'valid',
                sessionVersion,
                validatedAt: timestamp,
              }
            },
            async close() {
              calls.push('close')
            },
          },
        },
      })
    },
    { teamId, personId, shopId, timestamp, pendingCapture },
  )
  const shop = () => ({
    shop_id: shopId,
    display_name: '隔离登录契约店铺',
    platform: 'douyin',
    platform_shop_id: 'synthetic-platform-shop',
    enabled: true,
    owner_user_id: null,
    note: null,
    operating_start_date: null,
    created_at: timestamp,
    updated_at: timestamp,
    deleted_at: null,
    session_status: status,
  })
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() !== 'GET') writes.push(`${request.method()} ${path}`)
    let data: unknown
    if (path === '/api/v1/auth/me')
      data = { user_id: personId, display_name: '隔离契约验证' }
    else if (path === '/api/v1/access/me/teams')
      data = [
        {
          membership_id: 'contract-membership',
          team_id: teamId,
          team_name: '隔离团队',
          team_enabled: true,
          membership_enabled: true,
          role_code: 'member',
          data_scope: 'team',
        },
      ]
    else if (path === '/api/v1/access-management/me/module-access')
      data = {
        module_codes: ['shop'],
        is_super_account: superAccount,
        is_access_administrator: superAccount,
      }
    else if (path === '/api/v1/shops')
      data = { items: [shop()], total: 1, page: 1, page_size: 10 }
    else if (path === '/api/v1/users')
      data = { items: [], total: 0, page: 1, page_size: 100 }
    else if (path === `/api/v1/shops/${shopId}`) data = shop()
    else if (path === `/api/v1/shops/${shopId}/device-bindings`) data = []
    else if (path === `/api/v1/shops/${shopId}/credential`)
      data = {
        credential_id: null,
        configured: false,
        enabled: false,
        platform: 'douyin',
        masked_identifier: null,
        preferred_verification_channel: null,
        updated_at: null,
      }
    else if (path === `/api/v1/shops/${shopId}/session`)
      data = {
        session_id: 'contract-session',
        configured: true,
        status,
        version,
        source_device_id: null,
        captured_at: timestamp,
        validated_at: timestamp,
        expires_at: null,
        refresh_in_progress: false,
        refresh_lease_expires_at: null,
      }
    else if (path === `/api/v1/shops/${shopId}/session/refresh-lease`)
      data = {
        shop_id: shopId,
        lease_id: 'contract-lease',
        expected_version: version,
        expires_at: timestamp,
      }
    else if (
      path === `/api/v1/shops/${shopId}/session/refresh-lease/contract-lease` &&
      request.method() === 'DELETE'
    ) {
      await route.fulfill({ status: 204 })
      return
    } else if (path === `/api/v1/shops/${shopId}/session/health-check`) {
      if (healthFailure === 'auth') status = 'invalid'
      await route.fulfill({
        status: healthFailure === 'auth' ? 401 : 502,
        json: {
          code:
            healthFailure === 'auth'
              ? 'AUTH_INVALID'
              : 'PLATFORM_REQUEST_FAILED',
          message: '脱敏契约测试失败',
          details: {},
        },
      })
      return
    } else {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: data })
  })
  await page.goto('/#/shops')
  await expect(
    page.getByText('隔离登录契约店铺', { exact: true }).first(),
  ).toBeVisible()
  return {
    unexpected,
    writes,
    setAuthFailure() {
      healthFailure = 'auth'
    },
  }
}

test('Real list/detail share fresh login feedback; retained focus creates no further lease or save', async ({
  page,
}, info) => {
  const evidence = await prepare(page, true)
  const row = page.locator('tbody tr').filter({ hasText: '隔离登录契约店铺' })
  await expect(row.locator('.shop-list-table__actions button')).toHaveText([
    '查看',
    '登录',
    '停用',
    '移除',
  ])
  await row.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByText('登录状态已更新', { exact: true })).toBeVisible()
  expect(evidence.writes).toEqual([
    `POST /api/v1/shops/${shopId}/session/refresh-lease`,
  ])
  await row.getByRole('button', { name: '查看', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  await expect(drawer.getByText('v2', { exact: true })).toBeVisible()
  const before = [...evidence.writes]
  await drawer.getByRole('button', { name: '登录', exact: true }).click()
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (
            window as typeof window & { syncContractCalls: string[] }
          ).syncContractCalls.filter((x) => x === 'focus').length,
      ),
    )
    .toBe(2)
  expect(evidence.writes).toEqual(before)
  expect(
    await page.evaluate(
      () =>
        (
          window as typeof window & { syncContractCalls: string[] }
        ).syncContractCalls.filter((x) => x === 'refresh').length,
    ),
  ).toBe(1)
  await drawer.getByRole('button', { name: '验证会话', exact: true }).click()
  await expect(
    page.getByText('本次验证未完成，请稍后重试或点击登录', { exact: true }),
  ).toBeVisible()
  await expect(drawer.getByText('v2', { exact: true })).toBeVisible()
  evidence.setAuthFailure()
  await drawer.getByRole('button', { name: '验证会话', exact: true }).click()
  await expect(
    page.getByText('登录状态已失效，请点击登录重新授权', { exact: true }),
  ).toBeVisible()
  await expect(page).toHaveURL(/#\/shops$/)
  await expect(
    drawer.getByRole('button', { name: '登录', exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: info.outputPath('real-contract-shop-login-detail.png'),
  })
  expect(evidence.unexpected).toEqual([])
})

test('opened capture remains focusable in list and detail while only pending focus is disabled', async ({
  page,
}, info) => {
  const evidence = await prepare(page, true, true)
  const row = page.locator('tbody tr').filter({ hasText: '隔离登录契约店铺' })
  await row.getByRole('button', { name: '登录', exact: true }).click()
  const login = row.getByRole('button', { name: /登录中…$/ })
  await expect(login).toBeEnabled()
  await login.click()
  await expect(login).toBeDisabled()
  await row.getByRole('button', { name: '查看', exact: true }).click()
  const drawer = page.locator('.n-drawer')
  const detailLogin = drawer.getByRole('button', {
    name: /登录中…$/,
  })
  await expect(detailLogin).toBeDisabled()
  await page.evaluate(() =>
    (
      window as typeof window & { finishFocusContract: () => void }
    ).finishFocusContract(),
  )
  await expect(detailLogin).toBeEnabled()
  expect(evidence.writes).toEqual([
    `POST /api/v1/shops/${shopId}/session/refresh-lease`,
  ])
  const calls = await page.evaluate(
    () =>
      (window as typeof window & { syncContractCalls: string[] })
        .syncContractCalls,
  )
  expect(calls.filter((call) => call === 'focus')).toHaveLength(2)
  expect(calls.filter((call) => call === 'open')).toHaveLength(1)
  expect(calls.filter((call) => call === 'refresh')).toHaveLength(0)
  await page.screenshot({
    path: info.outputPath('browser-intercepted-opened-focusable-detail.png'),
  })
  await drawer.getByRole('button', { name: '取消登录', exact: true }).click()
  await expect(
    drawer.getByRole('button', { name: '登录', exact: true }),
  ).toBeEnabled()
  await expect
    .poll(() => evidence.writes)
    .toEqual([
      `POST /api/v1/shops/${shopId}/session/refresh-lease`,
      `DELETE /api/v1/shops/${shopId}/session/refresh-lease/contract-lease`,
    ])
  expect(evidence.unexpected).toEqual([])
})

test('ordinary team member has no list or detail login entry and submits no lease', async ({
  page,
}) => {
  const evidence = await prepare(page, false)
  await expect(
    page.getByRole('button', { name: '登录', exact: true }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: '查看', exact: true }).click()
  await expect(
    page.locator('.n-drawer').getByText('Session 版本', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '登录', exact: true }),
  ).toHaveCount(0)
  expect(evidence.writes).toEqual([])
  expect(evidence.unexpected).toEqual([])
})
