import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

test.skip(
  process.env.PLAYWRIGHT_API_MODE !== 'real',
  'Parameter preset browser coverage requires the isolated real PostgreSQL API.',
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
const teamId = '8fbd60bd-b1dc-4dc7-b828-4bce95d27791'
const userId = 'a6b227f6-d309-4ec2-84eb-a09c78b6d857'
const membershipId = 'cf933787-22d9-47f2-82da-190c4a8e59e7'
const deviceId = '6e018f80-5513-4109-b2a7-bc3e5e211643'
const shopAId = '696ba34a-ac79-4376-9a61-2ac53c1cea46'
const shopBId = '9833250c-9c5c-4531-9d1b-b50e9b76e83c'
const appId = 'preset-usability-zero-schema'
const loginName = 'preset-usability-e2e'
const password = 'preset-usability-e2e-password'

function runBackendScript(lines: string[]): void {
  execFileSync(backendPython, ['-c', lines.join('\n')], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
}

function cleanupFixture(): void {
  runBackendScript([
    'from uuid import UUID',
    'from sqlalchemy import delete',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership',
    'from app.modules.audit.models import AuditLog',
    'from app.modules.automation_apps.models import AutomationApplicationConfig, AutomationParameterPreset',
    'from app.modules.devices.models import Device',
    'from app.modules.human_auth.models import HumanSession',
    'from app.modules.shops.models import Shop, ShopDeviceBinding',
    'from app.modules.users.models import User',
    'from app.modules.workers.models import DeviceProviderInventory, DeviceRuntime, DeviceSkillCapability',
    `team_id = UUID(${JSON.stringify(teamId)})`,
    `user_id = UUID(${JSON.stringify(userId)})`,
    `membership_id = UUID(${JSON.stringify(membershipId)})`,
    `device_id = UUID(${JSON.stringify(deviceId)})`,
    `shop_ids = [UUID(${JSON.stringify(shopAId)}), UUID(${JSON.stringify(shopBId)})]`,
    `app_id = ${JSON.stringify(appId)}`,
    'with Session(get_database_engine()) as session:',
    '    session.execute(delete(AutomationParameterPreset).where(AutomationParameterPreset.team_id == team_id))',
    '    session.execute(delete(AutomationApplicationConfig).where(AutomationApplicationConfig.provider_code == "yingdao", AutomationApplicationConfig.app_id == app_id))',
    '    session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.shop_id.in_(shop_ids)))',
    '    session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))',
    '    session.execute(delete(DeviceProviderInventory).where(DeviceProviderInventory.device_id == device_id))',
    '    session.execute(delete(DeviceSkillCapability).where(DeviceSkillCapability.device_id == device_id))',
    '    session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))',
    '    session.execute(delete(Device).where(Device.device_id == device_id))',
    '    session.execute(delete(AuditLog).where(AuditLog.actor_user_id == user_id))',
    '    session.execute(delete(HumanSession).where(HumanSession.user_id == user_id))',
    '    session.execute(delete(MembershipModuleAccess).where(MembershipModuleAccess.membership_id == membership_id))',
    '    session.execute(delete(TeamMembership).where(TeamMembership.membership_id == membership_id))',
    '    session.execute(delete(User).where(User.user_id == user_id))',
    '    session.execute(delete(Team).where(Team.team_id == team_id))',
    '    session.commit()',
  ])
}

function seedFixture(): void {
  cleanupFixture()
  runBackendScript([
    'from datetime import UTC, datetime',
    'from uuid import UUID',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.enums import DataScope',
    'from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership',
    'from app.modules.devices.models import Device',
    'from app.modules.human_auth.passwords import PasswordService',
    'from app.modules.shops.enums import ShopPlatform',
    'from app.modules.shops.models import Shop, ShopDeviceBinding',
    'from app.modules.users.models import User',
    'from app.modules.workers.models import DeviceProviderInventory, DeviceRuntime, DeviceSkillCapability',
    `team_id = UUID(${JSON.stringify(teamId)})`,
    `user_id = UUID(${JSON.stringify(userId)})`,
    `membership_id = UUID(${JSON.stringify(membershipId)})`,
    `device_id = UUID(${JSON.stringify(deviceId)})`,
    `shop_a = UUID(${JSON.stringify(shopAId)})`,
    `shop_b = UUID(${JSON.stringify(shopBId)})`,
    `app_id = ${JSON.stringify(appId)}`,
    `password = ${JSON.stringify(password)}`,
    'now = datetime.now(UTC)',
    'inventory = {"provider":"yingdao","available":True,"status":"ready","status_reason_code":None,"status_reason":None,"provider_version":"6.3.6","execution_available":True,"execution_version":"6.3.6","execution_unavailable_reason":None,"logged_in":True,"account_display":"Preset usability fixture","account_type":"PersonalBasic","enterprise_account":False,"user_id":"900000000000000111","applications":[{"app_id":app_id,"app_name":"日常采集（零字段）","version_id":"1","updated_at":None,"app_type":None,"group_id":None}],"discovered_at":now.isoformat()}',
    'with Session(get_database_engine()) as session:',
    '    session.add(Team(team_id=team_id, name="Parameter preset usability team", enabled=True))',
    '    session.add(User(user_id=user_id, display_name="参数预设验收", login_name="preset-usability-e2e", password_hash=PasswordService().hash_password(password), enabled=True))',
    '    session.flush()',
    '    session.add(TeamMembership(membership_id=membership_id, team_id=team_id, user_id=user_id, role_code="member", data_scope=DataScope.TEAM, enabled=True))',
    '    session.flush()',
    '    session.add_all([MembershipModuleAccess(membership_id=membership_id, module_code="device"), MembershipModuleAccess(membership_id=membership_id, module_code="shop"), MembershipModuleAccess(membership_id=membership_id, module_code="schedule"), MembershipModuleAccess(membership_id=membership_id, module_code="task")])',
    '    session.add_all([Device(device_id=device_id, team_id=team_id, display_name="参数预设验收设备", enabled=True), DeviceRuntime(device_id=device_id, worker_version="0.4.9", last_seen_at=now, started_at=now, connection_status="online"), DeviceSkillCapability(device_id=device_id, skill_id="yingdao.app.run", display_name="Run Yingdao application", runtime="rpa", provider_code="yingdao", skill_version="1", classification="internal"), DeviceProviderInventory(device_id=device_id, provider_code="yingdao", available=True, provider_version="6.3.6", account_display="Preset usability fixture", account_type="PersonalBasic", enterprise_account=False, last_discovered_at=now, inventory_payload=inventory)])',
    '    session.add_all([Shop(shop_id=shop_a, display_name="甲店", platform=ShopPlatform.DOUYIN, enabled=True), Shop(shop_id=shop_b, display_name="乙店", platform=ShopPlatform.DOUYIN, enabled=True), ShopDeviceBinding(shop_id=shop_a, device_id=device_id, enabled=True), ShopDeviceBinding(shop_id=shop_b, device_id=device_id, enabled=True)])',
    '    session.commit()',
  ])
}

async function selectNumberParameterType(
  page: Page,
  row: Locator,
): Promise<void> {
  await row.locator('.n-base-selection').click()
  // Naive UI retains the leaving menu briefly while the next row's menu enters.
  const menu = page.locator('.n-base-select-menu:visible').last()
  await expect(menu).toBeVisible()
  await menu.getByText('数字', { exact: true }).click()
}

test.beforeAll(seedFixture)
test.afterAll(cleanupFixture)

test('creates fields from a zero-schema app, preserves the preset draft, and reads it back', async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000)
  await page.goto('/#/parameter-presets')
  await expect(page).toHaveURL(/#\/login\?redirect=\/parameter-presets/)
  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/parameter-presets$/)

  await page.getByRole('button', { name: '+ 新建配置' }).click()
  const presetDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理参数预设' })
  const applicationSelect = presetDialog.locator('.n-base-selection').first()
  await expect(applicationSelect).not.toHaveClass(/n-base-selection--disabled/)
  await applicationSelect.click()
  await page.getByText('日常采集（零字段）', { exact: true }).last().click()
  await expect(presetDialog).toContainText('该应用尚未配置参数字段')
  const presetName = presetDialog.locator(
    'input[name="automation-parameter-preset-name"]',
  )
  await presetName.fill('日常采集')
  await page.screenshot({
    path: testInfo.outputPath('01-zero-schema-preset-draft.png'),
    fullPage: true,
  })
  await presetDialog.getByRole('button', { name: '配置字段' }).click()

  const schemaDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '配置参数 · 日常采集（零字段）' })
  await schemaDialog.getByRole('button', { name: '+ 添加参数' }).click()
  await schemaDialog.getByRole('button', { name: '+ 添加参数' }).click()
  const rows = schemaDialog.getByTestId('parameter-config-field')
  await rows.nth(0).getByPlaceholder('例如 商品列表').fill('页码')
  await rows.nth(0).getByPlaceholder('例如 商品 ID').fill('页码')
  await selectNumberParameterType(page, rows.nth(0))
  await rows.nth(1).getByPlaceholder('例如 商品列表').fill('每页数量')
  await rows.nth(1).getByPlaceholder('例如 商品 ID').fill('每页数量')
  await selectNumberParameterType(page, rows.nth(1))
  await page.screenshot({
    path: testInfo.outputPath('02-shared-schema-fields.png'),
    fullPage: true,
  })
  await schemaDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(schemaDialog).toHaveCount(0)

  await expect(presetName).toHaveValue('日常采集')
  await expect(presetDialog).toContainText('当前应用已有 2 个共用参数字段')
  const publicParameterInputs = presetDialog
    .getByRole('heading', { name: '公共参数' })
    .locator('..')
    .locator('.n-input-number input')
  await publicParameterInputs.nth(0).fill('1')
  await publicParameterInputs.nth(1).fill('20')
  await presetDialog.getByRole('checkbox', { name: '甲店' }).click()
  await presetDialog.getByRole('checkbox', { name: '乙店' }).click()
  await expect(presetDialog).toContainText('本店生效值先继承公共参数')
  const shopA = presetDialog
    .locator('.preset-manager__shop')
    .filter({ hasText: '甲店' })
  const shopB = presetDialog
    .locator('.preset-manager__shop')
    .filter({ hasText: '乙店' })
  await shopA.locator('.n-input-number input').first().fill('2')
  await shopB.locator('.n-input-number input').first().fill('3')
  await expect(shopA).toContainText('恢复继承 · 页码')
  await expect(shopB).toContainText('恢复继承 · 页码')
  await page.screenshot({
    path: testInfo.outputPath('03-shop-override-editing.png'),
    fullPage: true,
  })
  await presetDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(presetDialog).toHaveCount(0)

  await expect(page.getByText('日常采集', { exact: true })).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('04-preset-list-readback.png'),
    fullPage: true,
  })
  await page.reload()
  await expect(page.getByText('日常采集', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const reopened = page
    .locator('.app-dialog')
    .filter({ hasText: '管理参数预设' })
  await expect(
    reopened.locator('input[name="automation-parameter-preset-name"]'),
  ).toHaveValue('日常采集')
  await expect(reopened).toContainText('当前应用已有 2 个共用参数字段')
  const reopenedPublic = reopened
    .getByRole('heading', { name: '公共参数' })
    .locator('..')
    .locator('.n-input-number input')
  await expect(reopenedPublic.nth(0)).toHaveValue('1')
  await expect(reopenedPublic.nth(1)).toHaveValue('20')
  const reopenedShopA = reopened
    .locator('.preset-manager__shop')
    .filter({ hasText: '甲店' })
  const reopenedShopB = reopened
    .locator('.preset-manager__shop')
    .filter({ hasText: '乙店' })
  await expect(reopenedShopA.locator('.n-input-number input').first()).toHaveValue('2')
  await expect(reopenedShopB.locator('.n-input-number input').first()).toHaveValue('3')

  await reopenedShopB.locator('.n-input-number input').first().fill('5')
  await reopened.getByRole('button', { name: '保存', exact: true }).click()
  await expect(reopened).toHaveCount(0)
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const resetDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理参数预设' })
  const resetShopA = resetDialog
    .locator('.preset-manager__shop')
    .filter({ hasText: '甲店' })
  const resetShopB = resetDialog
    .locator('.preset-manager__shop')
    .filter({ hasText: '乙店' })
  await expect(resetShopA.locator('.n-input-number input').first()).toHaveValue('2')
  await expect(resetShopB.locator('.n-input-number input').first()).toHaveValue('5')
  await resetShopB.getByRole('button', { name: '恢复继承 · 页码' }).click()
  await expect(resetShopB.getByRole('button', { name: '恢复继承 · 页码' })).toHaveCount(0)
  await resetDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(resetDialog).toHaveCount(0)
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const finalDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理参数预设' })
  const inheritedShopB = finalDialog
    .locator('.preset-manager__shop')
    .filter({ hasText: '乙店' })
  await expect(inheritedShopB.locator('.n-input-number input').first()).toHaveValue('1')

  await finalDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(finalDialog).toHaveCount(0)
  await page.getByRole('button', { name: '复制', exact: true }).click()
  const copyDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理参数预设' })
  await copyDialog.getByPlaceholder('复制后的名称').fill('日常采集副本')
  await copyDialog.getByRole('button', { name: '复制', exact: true }).click()
  await expect(copyDialog).toHaveCount(0)
  await expect(page.getByText('日常采集副本', { exact: true })).toBeVisible()
})
