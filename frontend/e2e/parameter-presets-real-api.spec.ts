import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import {
  expect,
  test,
  type APIResponse,
  type Locator,
  type Page,
} from '@playwright/test'

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

async function savePresetAndWait(
  page: Page,
  dialog: Locator,
): Promise<APIResponse> {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/parameter-presets') &&
      ['POST', 'PATCH'].includes(response.request().method()),
  )
  await dialog.getByRole('button', { name: '保存配置', exact: true }).click()
  const response = await responsePromise
  expect([200, 201]).toContain(response.status())
  return response
}

test.beforeAll(seedFixture)
test.afterAll(cleanupFixture)

test('saves a preset repeatedly, keeps public and shop editing together, and removes a legacy value', async ({
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
  const presetDialog = page.locator('.app-dialog').filter({
    has: page.locator('input[name="automation-parameter-preset-name"]'),
  })
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
  await presetDialog.getByRole('button', { name: '管理字段' }).click()

  const schemaDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理预设字段 · 日常采集（零字段）' })
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
    path: testInfo.outputPath('02-preset-schema-fields.png'),
    fullPage: true,
  })
  await schemaDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(schemaDialog).toHaveCount(0)

  await expect(presetName).toHaveValue('日常采集')
  const addCommonParameter = presetDialog.locator(
    '.preset-manager__add-parameter .n-base-selection',
  )
  await addCommonParameter.click()
  await page
    .locator('.n-base-select-menu:visible')
    .last()
    .getByText('页码', { exact: true })
    .click()
  await addCommonParameter.click()
  await page
    .locator('.n-base-select-menu:visible')
    .last()
    .getByText('每页数量', { exact: true })
    .click()
  await expect(presetDialog).toContainText('2 项当前参数')
  const publicParameterInputs = presetDialog.locator('.n-input-number input')
  await publicParameterInputs.nth(0).fill('1')
  await publicParameterInputs.nth(1).fill('20')
  await page.screenshot({
    path: testInfo.outputPath('03-compact-main-editor.png'),
    fullPage: true,
  })

  const addShop = presetDialog.locator(
    '.preset-manager__add-shop .n-base-selection',
  )
  await addShop.click()
  await page
    .locator('.n-base-select-menu:visible')
    .last()
    .getByText('甲店', { exact: true })
    .click()
  const shopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await expect(shopEditor).toContainText('字段')
  await expect(shopEditor).toContainText('公共值')
  await expect(shopEditor).toContainText('本店值')
  await shopEditor.locator('.n-input-number input').first().fill('2')
  await shopEditor.getByRole('button', { name: '确定', exact: true }).click()
  await expect(shopEditor).toHaveCount(0)

  await addShop.click()
  await page
    .locator('.n-base-select-menu:visible')
    .last()
    .getByText('乙店', { exact: true })
    .click()
  const cancelledShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 乙店' })
  await cancelledShopEditor.locator('.n-input-number input').first().fill('3')
  await cancelledShopEditor.getByRole('button', { name: '取消', exact: true }).click()
  await expect(cancelledShopEditor).toHaveCount(0)
  await expect(
    presetDialog.locator('.preset-manager__shop-row').filter({ hasText: '乙店' }),
  ).toHaveCount(0)

  const shopRow = presetDialog
    .locator('.preset-manager__shop-row')
    .filter({ hasText: '甲店' })
  await shopRow.getByRole('button', { name: '修改', exact: true }).click()
  const reopenedShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await expect(
    reopenedShopEditor.locator('.n-input-number input').first(),
  ).toHaveValue('2')
  await reopenedShopEditor
    .getByRole('button', { name: '恢复', exact: true })
    .first()
    .click()
  await reopenedShopEditor
    .getByRole('button', { name: '确定', exact: true })
    .click()
  await expect(shopRow).toContainText('使用公共参数')

  await shopRow.getByRole('button', { name: '修改', exact: true }).click()
  const overrideShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await overrideShopEditor.locator('.n-input-number input').first().fill('2')
  await expect(overrideShopEditor).toHaveCSS('opacity', '1')
  await page.screenshot({
    path: testInfo.outputPath('04-compact-shop-override-editor.png'),
    fullPage: true,
  })
  await overrideShopEditor
    .getByRole('button', { name: '确定', exact: true })
    .click()

  const created = await savePresetAndWait(page, presetDialog)
  const createdPreset = (await created.json()) as { preset_id: string }
  await expect(presetDialog).toBeVisible()
  await publicParameterInputs.nth(0).fill('5')
  await savePresetAndWait(page, presetDialog)
  await publicParameterInputs.nth(0).fill('1')
  await savePresetAndWait(page, presetDialog)
  await expect(presetDialog).toBeVisible()
  await presetDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(presetDialog).toHaveCount(0)

  await expect(page.getByText('日常采集', { exact: true })).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('05-final-preset-list.png'),
    fullPage: true,
  })

  runBackendScript([
    'from uuid import UUID',
    'from sqlalchemy import text',
    'from app.core.database import get_database_engine',
    `preset_id = UUID(${JSON.stringify(createdPreset.preset_id)})`,
    'with get_database_engine().begin() as connection:',
    '    result = connection.execute(',
    '        text("UPDATE automation_parameter_presets SET common_parameters = common_parameters || CAST(:legacy AS jsonb) WHERE preset_id = :preset_id"),',
    '        {"legacy": \'{"1":"旧值"}\', "preset_id": preset_id},',
    '    )',
    '    assert result.rowcount == 1',
  ])
  await page.reload()
  await expect(page.getByText('日常采集', { exact: true })).toBeVisible()
  await expect(page.getByText('待修正', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const reopened = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await expect(
    reopened.locator('input[name="automation-parameter-preset-name"]'),
  ).toHaveValue('日常采集')
  await expect(reopened).toContainText('2 项当前参数')
  const reopenedPublic = reopened.locator('.n-input-number input')
  await expect(reopenedPublic.nth(0)).toHaveValue('1')
  await expect(reopenedPublic.nth(1)).toHaveValue('20')
  await expect(reopened).toContainText('待修正字段')
  await expect(reopened).toContainText('1：旧值')
  await expect(
    reopened.locator('.preset-manager__shop-row').filter({ hasText: '甲店' }),
  ).toContainText('页码：2')
  await page.screenshot({
    path: testInfo.outputPath('06-final-legacy-field.png'),
    fullPage: true,
  })
  await reopened.getByRole('button', { name: '移除旧值', exact: true }).click()
  await savePresetAndWait(page, reopened)
  await expect(reopened).not.toContainText('待修正字段')
  await reopened.getByRole('button', { name: '取消', exact: true }).click()

  await page.getByRole('button', { name: '复制', exact: true }).click()
  const copyDialog = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await expect(
    copyDialog.locator('input[name="automation-parameter-preset-name"]'),
  ).toHaveValue('日常采集 副本')
  const copyPublicInputs = copyDialog.locator('.n-input-number input')
  await expect(copyPublicInputs).toHaveCount(2)
  await copyDialog
    .locator('.preset-manager__parameter-viewport')
    .getByRole('button', { name: '移除', exact: true })
    .last()
    .click()
  await expect(copyPublicInputs).toHaveCount(1)
  await copyPublicInputs.first().fill('6')
  const copiedShopRow = copyDialog
    .locator('.preset-manager__shop-row')
    .filter({ hasText: '甲店' })
  await copiedShopRow.getByRole('button', { name: '修改', exact: true }).click()
  const copiedShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await copiedShopEditor.locator('.n-input-number input').first().fill('7')
  await copiedShopEditor.getByRole('button', { name: '确定', exact: true }).click()
  const copiedSave = await savePresetAndWait(page, copyDialog)
  expect((await copiedSave.json()).common_parameters).toEqual({ 页码: 6 })
  expect((await copiedSave.json()).shop_overrides).toEqual(
    expect.objectContaining({ [shopAId]: { 页码: 7 } }),
  )
  await copyDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.getByText('日常采集 副本', { exact: true })).toBeVisible()
  const originalRow = page
    .getByRole('row')
    .filter({ has: page.getByText('日常采集', { exact: true }) })
  await originalRow.getByRole('button', { name: '编辑', exact: true }).click()
  const originalDialog = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await expect(originalDialog.locator('.n-input-number input')).toHaveCount(2)
  await expect(originalDialog.locator('.n-input-number input').first()).toHaveValue('1')
  await expect(originalDialog.locator('.n-input-number input').nth(1)).toHaveValue('20')
  await expect(
    originalDialog
      .locator('.preset-manager__shop-row')
      .filter({ hasText: '甲店' }),
  ).toContainText('页码：2')
  await originalDialog.getByRole('button', { name: '取消', exact: true }).click()
  const copyRow = page
    .getByRole('row')
    .filter({ hasText: '日常采集 副本' })
  await copyRow.getByRole('button', { name: '删除', exact: true }).click()
  const deleteDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '删除配置' })
  await expect(deleteDialog).toContainText('日常采集 副本')
  await deleteDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(deleteDialog).toHaveCount(0)
  await expect(copyRow).toBeVisible()
  await copyRow.getByRole('button', { name: '删除', exact: true }).click()
  await expect(deleteDialog).toContainText('日常采集 副本')
  const deleteResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/parameter-presets/') &&
      response.request().method() === 'DELETE',
  )
  await deleteDialog
    .getByRole('button', { name: '删除配置', exact: true })
    .click()
  expect((await deleteResponse).status()).toBe(204)
  await expect(page.getByText('日常采集 副本', { exact: true })).toHaveCount(0)

  const denseSchema = {
    fields: Array.from({ length: 10 }, (_, index) => ({
      name: `额外字段${index + 1}`,
      label: `额外字段 ${index + 1}`,
      type: 'text',
      required: false,
      default_value: '',
      options: [],
    })),
  }
  const originalSchema = {
    fields: [
      {
        name: '页码',
        label: '页码',
        type: 'number',
        required: false,
        default_value: 1,
        options: [],
      },
      {
        name: '每页数量',
        label: '每页数量',
        type: 'number',
        required: false,
        default_value: 20,
        options: [],
      },
    ],
  }
  const setPresetSnapshotAndParameters = (schema: object, parameters: object) =>
    runBackendScript([
      'import json',
      'from uuid import UUID',
      'from sqlalchemy import text',
      'from app.core.database import get_database_engine',
      `schema = json.loads(${JSON.stringify(JSON.stringify(schema))})`,
      `parameters = json.loads(${JSON.stringify(JSON.stringify(parameters))})`,
      `preset_id = UUID(${JSON.stringify(createdPreset.preset_id)})`,
      'with get_database_engine().begin() as connection:',
      '    result = connection.execute(',
      '        text("UPDATE automation_parameter_presets SET input_schema_snapshot = CAST(:schema AS jsonb), common_parameters = CAST(:parameters AS jsonb) WHERE preset_id = :preset_id"),',
      '        {"schema": json.dumps(schema), "parameters": json.dumps(parameters), "preset_id": preset_id},',
      '    )',
      '    assert result.rowcount == 1',
    ])

  setPresetSnapshotAndParameters(
    denseSchema,
    Object.fromEntries(denseSchema.fields.map((field) => [field.name, '值'])),
  )
  await page.setViewportSize({ width: 1440, height: 1200 })
  await page.reload()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const constrainedEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '编辑配置' })
  const parameterViewport = constrainedEditor.locator(
    '.preset-manager__parameter-viewport',
  )
  await expect(parameterViewport).toBeVisible()
  expect(
    await parameterViewport.evaluate(
      (element) => element.scrollHeight > element.clientHeight,
    ),
  ).toBe(true)
  expect(
    await parameterViewport.evaluate((element) => element.clientHeight),
  ).toBeGreaterThanOrEqual(8 * 60)
  const constrainedBox = await constrainedEditor.boundingBox()
  expect(constrainedBox).not.toBeNull()
  expect(constrainedBox!.y + constrainedBox!.height).toBeLessThanOrEqual(1200)
  await expect(
    constrainedEditor.getByRole('button', { name: '保存配置', exact: true }),
  ).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('07-compact-editor-eight-fields.png'),
    fullPage: true,
  })
  await parameterViewport.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await expect(constrainedEditor.getByText('额外字段 10', { exact: true })).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('08-compact-editor-scroll-bottom.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 1024, height: 640 })
  expect(
    await parameterViewport.evaluate(
      (element) => element.scrollHeight > element.clientHeight,
    ),
  ).toBe(true)
  const compactBox = await constrainedEditor.boundingBox()
  expect(compactBox).not.toBeNull()
  expect(compactBox!.y + compactBox!.height).toBeLessThanOrEqual(640)
  await expect(
    constrainedEditor.getByRole('button', { name: '保存配置', exact: true }),
  ).toBeVisible()
  await constrainedEditor.getByRole('button', { name: '取消', exact: true }).click()
  setPresetSnapshotAndParameters(originalSchema, { 页码: 1, 每页数量: 20 })
})

test('shows the same preset choice and per-shop final parameters before an immediate run', async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('control-center.theme-mode', 'dark')
  })
  await page.goto('/#/devices')
  await expect(page).toHaveURL(/#\/login\?redirect=\/devices/)
  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/devices$/)
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  const deviceRow = page
    .getByRole('row')
    .filter({ hasText: '参数预设验收设备' })
  await expect(deviceRow).toBeVisible()
  await deviceRow.getByRole('button', { name: '能力', exact: true }).click()
  const capabilityDrawer = page
    .getByRole('dialog')
    .filter({ hasText: '设备能力 · 参数预设验收设备' })
  await expect(capabilityDrawer).toContainText('日常采集（零字段）')
  const presetsResponse = page.waitForResponse(
    (response) =>
      response.url().includes(
        '/automation-app-configs/yingdao/preset-usability-zero-schema/parameter-presets',
      ) && response.request().method() === 'GET',
  )
  await capabilityDrawer
    .getByRole('button', { name: '运行', exact: true })
    .click()

  const runDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '运行应用 · 日常采集（零字段）' })
  const presetSelect = runDialog
    .locator('.n-form-item')
    .filter({ hasText: '参数预设' })
    .locator('.n-base-selection')
  expect((await presetsResponse).status()).toBe(200)
  await expect(presetSelect).toBeVisible()
  await presetSelect.click()
  const presetMenu = page.locator('.n-base-select-menu:visible').last()
  await expect(presetMenu).toBeVisible()
  await presetMenu.getByText('日常采集', { exact: true }).click()
  await expect(runDialog).toContainText(
    '已选择“日常采集”：2 家店铺，1 家有单独设置',
  )
  await runDialog.getByText('参数预设', { exact: true }).click()
  await expect(page.locator('.n-base-select-menu:visible')).toHaveCount(0)
  await page.screenshot({
    path: testInfo.outputPath('07-immediate-run-preset-choice.png'),
    fullPage: true,
  })

  await runDialog.getByRole('button', { name: '查看本次参数' }).click()
  await expect(runDialog).toContainText('甲店')
  await expect(runDialog).toContainText('乙店')
  await expect(runDialog).toContainText('页码')
  await expect(runDialog).toContainText('每页数量')
  await page.screenshot({
    path: testInfo.outputPath('08-immediate-run-parameter-preview.png'),
    fullPage: true,
  })

  await page.setViewportSize({ width: 1024, height: 720 })
  const dialogBox = await runDialog.boundingBox()
  expect(dialogBox).not.toBeNull()
  expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(720)
  expect(
    await page.evaluate(() => ({
      document:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
      body: document.body.scrollWidth > document.body.clientWidth,
    })),
  ).toEqual({ document: false, body: false })
  await page.screenshot({
    path: testInfo.outputPath('09-immediate-run-dark-narrow.png'),
    fullPage: true,
  })
})

test('keeps A and B field snapshots isolated after A extends its own schema', async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000)
  await page.goto('/#/parameter-presets')
  await expect(page).toHaveURL(/#\/login\?redirect=\/parameter-presets/)
  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/parameter-presets$/)

  const originalRow = page
    .getByRole('row')
    .filter({ has: page.getByText('日常采集', { exact: true }) })
  await expect(originalRow).toBeVisible()
  await originalRow.getByRole('button', { name: '复制', exact: true }).click()
  const copyDialog = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await expect(
    copyDialog.locator('input[name="automation-parameter-preset-name"]'),
  ).toHaveValue('日常采集 副本')
  await copyDialog.getByRole('button', { name: '取消', exact: true }).click()
  const copyRow = page
    .getByRole('row')
    .filter({ has: page.getByText('日常采集 副本', { exact: true }) })
  await expect(copyRow).toBeVisible()

  await originalRow.getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await editor.getByRole('button', { name: '管理字段' }).click()
  const schemaDialog = page
    .locator('.app-dialog')
    .filter({ hasText: '管理预设字段 · 日常采集（零字段）' })
  await schemaDialog.getByRole('button', { name: '+ 添加参数' }).click()
  const addedField = schemaDialog.getByTestId('parameter-config-field').last()
  await addedField.getByPlaceholder('例如 商品列表').fill('最大页数')
  await addedField.getByPlaceholder('例如 商品 ID').fill('最大页数')
  await selectNumberParameterType(page, addedField)
  await schemaDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(schemaDialog).toHaveCount(0)

  // A extends only its persisted schema. Adding the field still does not
  // select a public value until the editor explicitly adds it to A.
  await expect(editor).toContainText('2 项当前参数')
  await expect(
    editor.locator('.preset-manager__parameter-viewport').getByText('最大页数'),
  ).toHaveCount(0)
  const addCommonParameter = editor.locator(
    '.preset-manager__add-parameter .n-base-selection',
  )
  await addCommonParameter.click()
  await page
    .locator('.n-base-select-menu:visible')
    .last()
    .getByText('最大页数', { exact: true })
    .click()
  const aInputs = editor.locator('.n-input-number input')
  await expect(aInputs).toHaveCount(3)
  await aInputs.nth(2).fill('100')
  await savePresetAndWait(page, editor)

  const aShopRow = editor
    .locator('.preset-manager__shop-row')
    .filter({ hasText: '甲店' })
  await aShopRow.getByRole('button', { name: '修改', exact: true }).click()
  const aShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await expect(aShopEditor).toContainText('最大页数')
  await expect(aShopEditor).toHaveCSS('opacity', '1')
  await page.screenshot({
    path: testInfo.outputPath('10-a-shop-explicit-fields.png'),
    fullPage: true,
  })
  await aShopEditor.getByRole('button', { name: '取消', exact: true }).click()
  await editor.getByRole('button', { name: '取消', exact: true }).click()

  await copyRow.getByRole('button', { name: '编辑', exact: true }).click()
  const copyEditor = page.locator('.app-dialog').filter({ hasText: '编辑配置' })
  await expect(copyEditor.locator('.n-input-number input')).toHaveCount(2)
  await expect(copyEditor).not.toContainText('最大页数')
  const bShopRow = copyEditor
    .locator('.preset-manager__shop-row')
    .filter({ hasText: '甲店' })
  await bShopRow.getByRole('button', { name: '修改', exact: true }).click()
  const bShopEditor = page
    .locator('.app-dialog')
    .filter({ hasText: '店铺差异 · 甲店' })
  await expect(bShopEditor).not.toContainText('最大页数')
  await expect(bShopEditor).toHaveCSS('opacity', '1')
  await page.screenshot({
    path: testInfo.outputPath('11-b-shop-isolated-fields.png'),
    fullPage: true,
  })
  await bShopEditor.getByRole('button', { name: '取消', exact: true }).click()
  await copyEditor.getByRole('button', { name: '取消', exact: true }).click()
})
