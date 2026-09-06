import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { expect, test } from '@playwright/test'

test.skip(
  process.env.PLAYWRIGHT_API_MODE !== 'real',
  'Real Human Auth coverage',
)
test.describe.configure({ mode: 'serial' })

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url))
const backendDirectory = path.resolve(frontendDirectory, '../../backend')
const backendPython = path.join(
  backendDirectory,
  '.venv',
  'Scripts',
  'python.exe',
)
const loginName = 'human-auth-e2e'
const password = 'human-auth-e2e-password'

function runBackendScript(lines: string[]): void {
  execFileSync(backendPython, ['-c', lines.join('\n')], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
}

function seedHumanUser(): void {
  runBackendScript([
    'from sqlalchemy import delete, select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership',
    'from app.modules.human_auth.models import HumanSession',
    'from app.modules.human_auth.passwords import PasswordService',
    'from app.modules.users.models import User',
    'from app.shared.identifiers import generate_id',
    `login_name = ${JSON.stringify(loginName)}`,
    `password = ${JSON.stringify(password)}`,
    'with Session(get_database_engine()) as session:',
    '    existing = session.scalar(select(User).where(User.login_name == login_name))',
    '    if existing is not None:',
    '        session.execute(delete(HumanSession).where(HumanSession.user_id == existing.user_id))',
    '        membership_ids = list(session.scalars(select(TeamMembership.membership_id).where(TeamMembership.user_id == existing.user_id)))',
    '        if membership_ids:',
    '            session.execute(delete(MembershipModuleAccess).where(MembershipModuleAccess.membership_id.in_(membership_ids)))',
    '        session.execute(delete(TeamMembership).where(TeamMembership.user_id == existing.user_id))',
    '        session.delete(existing)',
    '        session.flush()',
    '    team = session.scalar(select(Team).where(Team.name == "默认团队"))',
    '    assert team is not None',
    '    user = User(user_id=generate_id(), display_name="认证回归人员", login_name=login_name, password_hash=PasswordService().hash_password(password), enabled=True)',
    '    session.add(user)',
    '    session.flush()',
    '    membership_id = generate_id()',
    '    session.add(TeamMembership(membership_id=membership_id, team_id=team.team_id, user_id=user.user_id, role_code="member", data_scope="team", enabled=True))',
    '    session.flush()',
    '    session.add(MembershipModuleAccess(membership_id=membership_id, module_code="shop"))',
    '    session.commit()',
  ])
}

function cleanupHumanUser(): void {
  runBackendScript([
    'from sqlalchemy import delete, select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import MembershipModuleAccess, TeamMembership',
    'from app.modules.human_auth.models import HumanSession',
    'from app.modules.users.models import User',
    `login_name = ${JSON.stringify(loginName)}`,
    'with Session(get_database_engine()) as session:',
    '    user = session.scalar(select(User).where(User.login_name == login_name))',
    '    if user is not None:',
    '        session.execute(delete(HumanSession).where(HumanSession.user_id == user.user_id))',
    '        membership_ids = list(session.scalars(select(TeamMembership.membership_id).where(TeamMembership.user_id == user.user_id)))',
    '        if membership_ids:',
    '            session.execute(delete(MembershipModuleAccess).where(MembershipModuleAccess.membership_id.in_(membership_ids)))',
    '        session.execute(delete(TeamMembership).where(TeamMembership.user_id == user.user_id))',
    '        session.delete(user)',
    '    session.commit()',
  ])
}

test.beforeAll(seedHumanUser)
test.afterAll(cleanupHumanUser)

test('real login restores the HttpOnly session and logout revokes it', async ({
  context,
  page,
}) => {
  await page.goto('/#/shops')
  await expect(page).toHaveURL(/#\/login\?redirect=\/shops/)
  await expect(page.getByRole('alert')).toHaveCount(0)

  const privilegedReferenceRequests: string[] = []
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname
    if (pathname === '/api/v1/users' || pathname === '/api/v1/devices') {
      privilegedReferenceRequests.push(pathname)
    }
  })
  let delayInitialShopList = true
  await page.route('**/api/v1/shops?page=*', async (route) => {
    if (delayInitialShopList) {
      delayInitialShopList = false
      await new Promise((resolve) => setTimeout(resolve, 200))
    }
    await route.continue()
  })

  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/#\/shops$/)
  await expect(page.getByRole('status')).toContainText('正在加载，请稍候…')
  await expect(page.getByRole('status')).toHaveCount(0)
  await expect(page.getByText('加载失败')).toHaveCount(0)
  expect(privilegedReferenceRequests).toEqual([])
  await page.unroute('**/api/v1/shops?page=*')
  await expect(
    page.getByRole('button', { name: '当前用户菜单' }),
  ).toContainText('认证回归人员')
  const sessionCookie = (await context.cookies()).find(
    (cookie) => cookie.name === 'siyu_human_session',
  )
  expect(sessionCookie).toMatchObject({
    httpOnly: true,
    sameSite: 'Lax',
    secure: false,
    path: '/api/v1',
  })

  await page.reload()
  await expect(page).toHaveURL(/#\/shops$/)
  await expect(
    page.getByRole('button', { name: '当前用户菜单' }),
  ).toContainText('认证回归人员')

  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await expect(page.getByText('当前团队：默认团队')).toBeVisible()
  await page.getByText('退出登录', { exact: true }).click()
  await expect(page).toHaveURL(/#\/login(?:\?redirect=\/shops)?$/)
  expect(
    (await context.cookies()).find(
      (cookie) => cookie.name === 'siyu_human_session',
    ),
  ).toBeUndefined()
})
