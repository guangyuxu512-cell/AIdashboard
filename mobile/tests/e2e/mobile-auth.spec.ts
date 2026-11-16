import { expect, test, type Page, type Route } from '@playwright/test'

import {
  createMobileAuthApiFixture,
  type MobileAuthApiFixture,
  type MobileAuthApiFixtureOptions,
} from './auth-api-fixture'

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function installAuthApi(
  page: Page,
  options: MobileAuthApiFixtureOptions = {},
): Promise<MobileAuthApiFixture> {
  const auth = createMobileAuthApiFixture(options)
  await page.route('**/api/v1/**', async (route) => {
    if (await auth.handle(route)) return

    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET' && path === '/api/v1/devices') {
      await fulfillJson(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      })
      return
    }
    if (request.method() === 'GET' && path === '/api/v1/tasks') {
      await fulfillJson(route, {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      })
      return
    }
    await route.fulfill({ status: 404 })
  })
  return auth
}

async function submitLogin(
  page: Page,
  loginName = 'operator',
  password = 'correct-password',
): Promise<void> {
  await page.getByPlaceholder('请输入登录账号').fill(loginName)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
}

const expectedHumanUnauthorizedResourceError =
  'Failed to load resource: the server responded with a status of 401 (Unauthorized)'

function collectUnexpectedConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (
      message.type() === 'error' &&
      message.text() !== expectedHumanUnauthorizedResourceError
    ) {
      errors.push(message.text())
    }
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true)
}

test('正确账号密码建立HttpOnly Session并进入首个有权模块', async ({
  page,
  context,
}) => {
  const consoleErrors = collectUnexpectedConsoleErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installAuthApi(page, { authenticated: false })
  await page.goto('/#/login')

  await submitLogin(page)

  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.getByTestId('mobile-global-header')).toContainText('设备')
  expect(auth.isAuthenticated()).toBe(true)
  expect(auth.teamHeaders).toContain('team-mobile-e2e')
  const cookies = await context.cookies()
  expect(cookies).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        name: 'siyu_human_session',
        httpOnly: true,
        sameSite: 'Lax',
      }),
    ]),
  )
  expect(consoleErrors).toEqual([])
})

test('错误密码只显示安全错误且不建立Session', async ({ page, context }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installAuthApi(page, { authenticated: false })
  await page.goto('/#/login')

  await submitLogin(page, 'operator', 'wrong-password')

  await expect(page).toHaveURL(/#\/login$/)
  await expect(page.getByRole('alert')).toHaveText('登录账号或密码错误')
  await expect(page.getByPlaceholder('请输入密码')).toHaveValue('')
  expect(auth.isAuthenticated()).toBe(false)
  expect(
    (await context.cookies()).some(
      (cookie) => cookie.name === 'siyu_human_session',
    ),
  ).toBe(false)
})

test('未登录深链跳转登录并在登录后返回原任务页', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installAuthApi(page, { authenticated: false })

  await page.goto('/#/tasks')

  await expect(page).toHaveURL(/#\/login\?redirect=\/tasks$/)
  await submitLogin(page)
  await expect(page).toHaveURL(/#\/tasks$/)
  await expect(page.getByTestId('mobile-global-header')).toContainText('任务')
})

test('刷新页面通过服务端Session恢复身份', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installAuthApi(page, { authenticated: false })
  await page.goto('/#/login')
  await submitLogin(page)
  await expect(page).toHaveURL(/#\/devices$/)

  await page.reload()

  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.getByTestId('mobile-global-header')).toContainText('设备')
})

test('服务端Session失效后回到登录页', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installAuthApi(page)
  await page.goto('/#/tasks')
  await expect(page).toHaveURL(/#\/tasks$/)

  auth.expireSession()
  await page.reload()

  await expect(page).toHaveURL(/#\/login\?redirect=\/tasks$/)
  await expect(
    page.getByRole('button', { name: '登录', exact: true }),
  ).toBeVisible()
})

test('退出登录撤销Session、清理上下文并回登录页', async ({ page, context }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installAuthApi(page)
  await page.goto('/#/me')

  await page.getByRole('button', { name: '退出登录' }).click()

  await expect(page).toHaveURL(/#\/login$/)
  expect(auth.isAuthenticated()).toBe(false)
  expect(
    (await context.cookies()).some(
      (cookie) => cookie.name === 'siyu_human_session',
    ),
  ).toBe(false)
})

test('device权限控制入口与直接URL访问', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installAuthApi(page, { moduleCodes: ['task'] })
  await page.goto('/#/tasks')

  await expect(
    page.getByTestId('mobile-bottom-navigation-devices'),
  ).toHaveCount(0)
  await expect(page.getByTestId('mobile-bottom-navigation-tasks')).toBeVisible()

  await page.goto('/#/devices')
  await expect(page).toHaveURL(/#\/permission-denied$/)
  await expect(page.getByText('无权访问', { exact: true })).toBeVisible()
})

test('task权限控制入口与直接URL访问', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installAuthApi(page, { moduleCodes: ['device'] })
  await page.goto('/#/devices')

  await expect(page.getByTestId('mobile-bottom-navigation-tasks')).toHaveCount(
    0,
  )
  await expect(
    page.getByTestId('mobile-bottom-navigation-devices'),
  ).toBeVisible()

  await page.goto('/#/tasks')
  await expect(page).toHaveURL(/#\/permission-denied$/)
})

test('多Team用户必须选择当前Team后再加载Module Access', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installAuthApi(page, {
    authenticated: false,
    teams: [
      {
        membershipId: 'membership-1',
        teamId: 'team-1',
        teamName: '默认团队',
        teamEnabled: true,
        membershipEnabled: true,
      },
      {
        membershipId: 'membership-2',
        teamId: 'team-2',
        teamName: '运营团队',
        teamEnabled: true,
        membershipEnabled: true,
      },
    ],
  })
  await page.goto('/#/login')
  await submitLogin(page)

  await expect(page.getByText('选择当前团队', { exact: true })).toBeVisible()
  expect(auth.teamHeaders).toEqual([])
  await page.getByText('运营团队', { exact: true }).click()
  await page.getByRole('button', { name: '进入中控台' }).click()

  await expect(page).toHaveURL(/#\/devices$/)
  expect(auth.teamHeaders).toEqual(['team-2'])
})

for (const width of [360, 375, 390, 430]) {
  for (const theme of ['light', 'dark'] as const) {
    test(`登录页 ${width}px ${theme} 无横向溢出`, async ({
      page,
    }, testInfo) => {
      const consoleErrors = collectUnexpectedConsoleErrors(page)
      await page.setViewportSize({ width, height: width === 360 ? 640 : 844 })
      await page.addInitScript((mode) => {
        window.localStorage.setItem('control-center.mobile.theme-mode', mode)
      }, theme)
      await installAuthApi(page, { authenticated: false })

      await page.goto('/#/login')

      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(
        page.getByRole('button', { name: '登录', exact: true }),
      ).toBeVisible()
      expect(
        (
          await page
            .getByRole('button', { name: '登录', exact: true })
            .boundingBox()
        )?.height,
      ).toBeGreaterThanOrEqual(44)
      await expectNoHorizontalOverflow(page)
      expect(consoleErrors).toEqual([])
      await page.screenshot({
        path: testInfo.outputPath(`mobile-auth-${width}-${theme}.png`),
        fullPage: true,
      })
    })
  }
}
