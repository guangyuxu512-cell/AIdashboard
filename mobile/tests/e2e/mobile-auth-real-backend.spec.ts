import {
  expect,
  request as playwrightRequest,
  test,
  type Page,
} from '@playwright/test'

const REAL_BACKEND_ENABLED = process.env.MOBILE_REAL_AUTH_E2E === '1'

interface RealBackendFixture {
  password: string
  teamA: string
  teamB: string
  deviceA: string
  deviceB: string
  taskA: string
  taskB: string
}

interface ApiProbeResult {
  status: number
  code: string | null
}

function requiredEnvironment(name: string): string {
  const value = process.env[name]?.trim()
  if (!value) throw new Error(`缺少真实 Mobile Auth E2E 环境变量：${name}`)
  return value
}

function realBackendFixture(): RealBackendFixture {
  return {
    password: requiredEnvironment('MOBILE_REAL_AUTH_PASSWORD'),
    teamA: requiredEnvironment('MOBILE_REAL_AUTH_TEAM_A'),
    teamB: requiredEnvironment('MOBILE_REAL_AUTH_TEAM_B'),
    deviceA: requiredEnvironment('MOBILE_REAL_AUTH_DEVICE_A'),
    deviceB: requiredEnvironment('MOBILE_REAL_AUTH_DEVICE_B'),
    taskA: requiredEnvironment('MOBILE_REAL_AUTH_TASK_A'),
    taskB: requiredEnvironment('MOBILE_REAL_AUTH_TASK_B'),
  }
}

async function submitLogin(
  page: Page,
  loginName: string,
  password: string,
): Promise<void> {
  await page.getByPlaceholder('请输入登录账号').fill(loginName)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
}

async function logoutThroughUi(page: Page): Promise<void> {
  await page.goto('/#/me')
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/#\/login$/)
}

async function probeApi(
  page: Page,
  path: string,
  teamId: string,
): Promise<ApiProbeResult> {
  return page.evaluate(
    async ({ requestPath, requestTeamId }) => {
      const response = await fetch(`/api/v1/${requestPath}`, {
        credentials: 'include',
        headers: { 'X-Team-ID': requestTeamId },
      })
      const payload = (await response.json().catch(() => null)) as {
        code?: unknown
      } | null
      return {
        status: response.status,
        code: typeof payload?.code === 'string' ? payload.code : null,
      }
    },
    { requestPath: path, requestTeamId: teamId },
  )
}

function collectTeamHeaders(page: Page, pathname: string): string[] {
  const headers: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === pathname) {
      const teamId = request.headers()['x-team-id']
      if (teamId) headers.push(teamId)
    }
  })
  return headers
}

test.describe('Mobile Auth V1 真实 Backend 闭环', () => {
  test.skip(
    !REAL_BACKEND_ENABLED,
    '仅在隔离真实 Backend 环境中运行；禁止指向受保护数据库。',
  )

  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
  })

  test('登录、HttpOnly Session恢复、失效与Logout形成真实闭环', async ({
    page,
    context,
  }) => {
    const fixture = realBackendFixture()
    await page.goto('/#/tasks')
    await expect(page).toHaveURL(/#\/login\?redirect=\/tasks$/)

    await submitLogin(page, 'mobile_full', 'wrong-password')
    await expect(page.getByRole('alert')).toHaveText('登录账号或密码错误')
    await expect(page).toHaveURL(/#\/login\?redirect=\/tasks$/)

    await submitLogin(page, 'mobile_full', fixture.password)
    await expect(page).toHaveURL(/#\/tasks$/)
    await expect(page.getByTestId('task-list')).toBeVisible()

    const sessionCookie = (await context.cookies()).find(
      (cookie) => cookie.name === 'siyu_human_session',
    )
    expect(sessionCookie).toMatchObject({
      httpOnly: true,
      sameSite: 'Lax',
      path: '/api/v1',
    })

    await page.reload()
    await expect(page).toHaveURL(/#\/tasks$/)
    await expect(page.getByTestId('task-list')).toBeVisible()

    const detachedSession = await playwrightRequest.newContext({
      baseURL: new URL(page.url()).origin,
      extraHTTPHeaders: {
        Cookie: `${sessionCookie?.name}=${sessionCookie?.value}`,
      },
    })
    const invalidationResponse = await detachedSession.post(
      '/api/v1/auth/logout',
    )
    expect(invalidationResponse.status()).toBe(204)
    await detachedSession.dispose()

    await page.reload()
    await expect(page).toHaveURL(/#\/login\?redirect=\/tasks$/)

    await submitLogin(page, 'mobile_full', fixture.password)
    await expect(page).toHaveURL(/#\/tasks$/)
    await logoutThroughUi(page)
    expect(
      (await context.cookies()).some(
        (cookie) => cookie.name === 'siyu_human_session',
      ),
    ).toBe(false)
  })

  test('多Team使用现有最小选择流程并发送所选X-Team-ID', async ({ page }) => {
    const fixture = realBackendFixture()
    const moduleHeaders = collectTeamHeaders(
      page,
      '/api/v1/access-management/me/module-access',
    )
    const deviceHeaders = collectTeamHeaders(page, '/api/v1/devices')

    await page.goto('/#/login')
    await submitLogin(page, 'mobile_multi', fixture.password)

    await expect(page.getByText('选择当前团队', { exact: true })).toBeVisible()
    await page.getByText('Mobile Auth 团队 B', { exact: true }).click()
    await page.getByRole('button', { name: '进入中控台' }).click()

    await expect(page).toHaveURL(/#\/devices$/)
    await expect(
      page.getByText('Mobile Auth B设备', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Mobile Auth A设备', { exact: true }),
    ).toHaveCount(0)
    expect(moduleHeaders).toContain(fixture.teamB)
    expect(deviceHeaders).toContain(fixture.teamB)
  })

  test('Device入口、Route、Backend Guard与跨Team隔离一致', async ({ page }) => {
    const fixture = realBackendFixture()
    const deviceHeaders = collectTeamHeaders(page, '/api/v1/devices')

    await page.goto('/#/login')
    await submitLogin(page, 'mobile_full', fixture.password)
    await expect(page).toHaveURL(/#\/devices$/)
    await expect(
      page.getByText('Mobile Auth A设备', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Mobile Auth 团队设备', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Mobile Auth B设备', { exact: true }),
    ).toHaveCount(0)
    expect(deviceHeaders).toContain(fixture.teamA)

    await page.goto(`/#/devices/${fixture.deviceA}`)
    await expect(page.getByTestId('device-detail')).toBeVisible()
    await expect(page.getByTestId('device-hero-name')).toHaveText(
      'Mobile Auth A设备',
    )

    await expect(
      probeApi(page, `devices/${fixture.deviceB}`, fixture.teamA),
    ).resolves.toEqual({ status: 404, code: 'DEVICE_NOT_FOUND' })

    await logoutThroughUi(page)
    await submitLogin(page, 'mobile_task', fixture.password)
    await expect(page).toHaveURL(/#\/tasks$/)
    await expect(
      page.getByTestId('mobile-bottom-navigation-devices'),
    ).toHaveCount(0)

    await page.goto('/#/devices')
    await expect(page).toHaveURL(/#\/permission-denied$/)
    await page.goto(`/#/devices/${fixture.deviceA}`)
    await expect(page).toHaveURL(/#\/permission-denied$/)

    await expect(probeApi(page, 'devices', fixture.teamA)).resolves.toEqual({
      status: 403,
      code: 'MODULE_ACCESS_DENIED',
    })
    await expect(
      probeApi(page, `devices/${fixture.deviceA}`, fixture.teamA),
    ).resolves.toEqual({ status: 403, code: 'MODULE_ACCESS_DENIED' })
  })

  test('Task列表、详情、Runtime Events及跨Team权限形成真实闭环', async ({
    page,
  }) => {
    const fixture = realBackendFixture()
    const taskHeaders = collectTeamHeaders(page, '/api/v1/tasks')

    await page.goto('/#/login')
    await submitLogin(page, 'mobile_full', fixture.password)
    await page.goto('/#/tasks')

    await expect(
      page.getByText('Mobile Auth 运行任务', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Mobile Auth 团队任务', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Mobile Auth B任务', { exact: true }),
    ).toHaveCount(0)
    expect(taskHeaders).toContain(fixture.teamA)

    await page.goto(`/#/tasks/${fixture.taskA}`)
    await expect(page.getByTestId('task-detail-title')).toHaveText(
      'Mobile Auth 运行任务',
    )
    await expect(page.getByTestId('runtime-events')).toContainText(
      '真实运行日志',
    )

    await expect(
      probeApi(page, `tasks/${fixture.taskB}`, fixture.teamA),
    ).resolves.toEqual({ status: 404, code: 'TASK_NOT_FOUND' })
    await expect(
      probeApi(page, `tasks/${fixture.taskB}/events?limit=50`, fixture.teamA),
    ).resolves.toEqual({ status: 404, code: 'TASK_NOT_FOUND' })

    await logoutThroughUi(page)
    await submitLogin(page, 'mobile_device', fixture.password)
    await expect(page).toHaveURL(/#\/devices$/)
    await expect(
      page.getByTestId('mobile-bottom-navigation-tasks'),
    ).toHaveCount(0)

    await page.goto('/#/tasks')
    await expect(page).toHaveURL(/#\/permission-denied$/)
    await page.goto(`/#/tasks/${fixture.taskA}`)
    await expect(page).toHaveURL(/#\/permission-denied$/)

    await expect(probeApi(page, 'tasks', fixture.teamA)).resolves.toEqual({
      status: 403,
      code: 'MODULE_ACCESS_DENIED',
    })
    await expect(
      probeApi(page, `tasks/${fixture.taskA}`, fixture.teamA),
    ).resolves.toEqual({ status: 403, code: 'MODULE_ACCESS_DENIED' })
    await expect(
      probeApi(page, `tasks/${fixture.taskA}/events?limit=50`, fixture.teamA),
    ).resolves.toEqual({ status: 403, code: 'MODULE_ACCESS_DENIED' })
  })
})
