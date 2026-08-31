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
    'from app.modules.access.models import Team, TeamMembership',
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
    '        session.execute(delete(TeamMembership).where(TeamMembership.user_id == existing.user_id))',
    '        session.delete(existing)',
    '        session.flush()',
    '    team = session.scalar(select(Team).where(Team.name == "默认团队"))',
    '    assert team is not None',
    '    user = User(user_id=generate_id(), display_name="认证回归人员", login_name=login_name, password_hash=PasswordService().hash_password(password), enabled=True)',
    '    session.add(user)',
    '    session.flush()',
    '    session.add(TeamMembership(membership_id=generate_id(), team_id=team.team_id, user_id=user.user_id, role_code="member", data_scope="team", enabled=True))',
    '    session.commit()',
  ])
}

function cleanupHumanUser(): void {
  runBackendScript([
    'from sqlalchemy import delete, select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import TeamMembership',
    'from app.modules.human_auth.models import HumanSession',
    'from app.modules.users.models import User',
    `login_name = ${JSON.stringify(loginName)}`,
    'with Session(get_database_engine()) as session:',
    '    user = session.scalar(select(User).where(User.login_name == login_name))',
    '    if user is not None:',
    '        session.execute(delete(HumanSession).where(HumanSession.user_id == user.user_id))',
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

  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/#\/shops$/)
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
  await expect(page).toHaveURL(/#\/login$/)
  expect(
    (await context.cookies()).find(
      (cookie) => cookie.name === 'siyu_human_session',
    ),
  ).toBeUndefined()
})
