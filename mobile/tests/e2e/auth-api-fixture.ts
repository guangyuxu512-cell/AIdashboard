import type { Page, Route } from '@playwright/test'

export interface AuthTeamFixture {
  membershipId: string
  teamId: string
  teamName: string
  teamEnabled: boolean
  membershipEnabled: boolean
}

export interface MobileAuthApiFixtureOptions {
  authenticated?: boolean
  loginName?: string
  password?: string
  moduleCodes?: string[]
  teams?: AuthTeamFixture[]
}

export interface MobileAuthApiFixture {
  readonly teamHeaders: Array<string | undefined>
  handle(route: Route): Promise<boolean>
  expireSession(): void
  isAuthenticated(): boolean
}

const defaultTeam: AuthTeamFixture = {
  membershipId: 'membership-mobile-e2e',
  teamId: 'team-mobile-e2e',
  teamName: '默认团队',
  teamEnabled: true,
  membershipEnabled: true,
}

function apiError(
  route: Route,
  status: number,
  code: string,
  message: string,
): Promise<void> {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify({
      code,
      message,
      request_id: 'request-mobile-auth-e2e',
      details: null,
    }),
  })
}

export function createMobileAuthApiFixture(
  options: MobileAuthApiFixtureOptions = {},
): MobileAuthApiFixture {
  let authenticated = options.authenticated ?? true
  const loginName = options.loginName ?? 'operator'
  const password = options.password ?? 'correct-password'
  const moduleCodes = options.moduleCodes ?? [
    'device',
    'task',
    'schedule',
    'shop',
  ]
  const teams = options.teams ?? [defaultTeam]
  const teamHeaders: Array<string | undefined> = []

  return {
    teamHeaders,

    async handle(route) {
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname

      if (path === '/api/v1/auth/login' && request.method() === 'POST') {
        const body = request.postDataJSON() as {
          login_name?: string
          password?: string
        }
        if (body.login_name !== loginName || body.password !== password) {
          await apiError(route, 401, 'HUMAN_LOGIN_FAILED', '登录账号或密码错误')
          return true
        }
        authenticated = true
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: {
            'set-cookie':
              'siyu_human_session=mobile-e2e-session; Path=/api/v1; HttpOnly; SameSite=Lax',
          },
          body: JSON.stringify({
            user_id: 'user-mobile-e2e',
            display_name: '移动端测试人员',
          }),
        })
        return true
      }

      if (path === '/api/v1/auth/logout' && request.method() === 'POST') {
        authenticated = false
        await route.fulfill({
          status: 204,
          headers: {
            'set-cookie':
              'siyu_human_session=; Path=/api/v1; HttpOnly; SameSite=Lax; Max-Age=0',
          },
        })
        return true
      }

      if (path === '/api/v1/auth/me' && request.method() === 'GET') {
        if (!authenticated) {
          await apiError(
            route,
            401,
            'HUMAN_AUTHENTICATION_REQUIRED',
            '需要有效的管理端用户身份',
          )
          return true
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            user_id: 'user-mobile-e2e',
            display_name: '移动端测试人员',
          }),
        })
        return true
      }

      if (path === '/api/v1/access/me/teams' && request.method() === 'GET') {
        if (!authenticated) {
          await apiError(
            route,
            401,
            'HUMAN_AUTHENTICATION_REQUIRED',
            '需要有效的管理端用户身份',
          )
          return true
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            teams.map((team) => ({
              membership_id: team.membershipId,
              team_id: team.teamId,
              team_name: team.teamName,
              team_enabled: team.teamEnabled,
              role_code: 'member',
              data_scope: 'team',
              membership_enabled: team.membershipEnabled,
            })),
          ),
        })
        return true
      }

      if (
        path === '/api/v1/access-management/me/module-access' &&
        request.method() === 'GET'
      ) {
        if (!authenticated) {
          await apiError(
            route,
            401,
            'HUMAN_AUTHENTICATION_REQUIRED',
            '需要有效的管理端用户身份',
          )
          return true
        }
        teamHeaders.push(request.headers()['x-team-id'])
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            module_codes: moduleCodes,
            is_access_administrator: false,
          }),
        })
        return true
      }

      return false
    },

    expireSession() {
      authenticated = false
    },

    isAuthenticated() {
      return authenticated
    },
  }
}

export async function installAuthenticatedMobileSession(
  page: Page,
  options: MobileAuthApiFixtureOptions = {},
): Promise<MobileAuthApiFixture> {
  const fixture = createMobileAuthApiFixture(options)
  await page.route('**/api/v1/**', async (route) => {
    if (await fixture.handle(route)) return
    await route.fulfill({ status: 404 })
  })
  return fixture
}
