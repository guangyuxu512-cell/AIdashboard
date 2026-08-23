import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE !== 'real', 'Real API mode coverage')
test.describe.configure({ mode: 'serial' })

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url))
const backendDirectory = path.resolve(frontendDirectory, '../../backend')
const backendPython = path.join(
  backendDirectory,
  '.venv',
  'Scripts',
  'python.exe',
)
const testPrefix = 'stage-2b-e2e-'

function cleanupRealTestData(): void {
  const cleanupScript = [
    'from sqlalchemy import delete, select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.automation_apps.models import AutomationApplicationConfig',
    'from app.modules.devices.models import Device',
    'from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding',
    'from app.modules.sessions.models import ShopSession',
    'from app.modules.shops.models import Shop, ShopDeviceBinding',
    'from app.modules.tasks.models import Task',
    'from app.modules.workers.models import DeviceProviderInventory, DeviceRuntime, WorkerDeviceCredential',
    `prefix = ${JSON.stringify(`${testPrefix}%`)}`,
    'with Session(get_database_engine()) as session:',
    '    session.execute(delete(AutomationApplicationConfig).where(AutomationApplicationConfig.app_id == "stage-3b-1a-app"))',
    '    shop_ids = list(session.scalars(select(Shop.shop_id).where(Shop.display_name.like(prefix))))',
    '    device_ids = list(session.scalars(select(Device.device_id).where(Device.display_name.like(prefix))))',
    '    if shop_ids:',
    '        credential_ids = list(session.scalars(select(ShopCredentialBinding.credential_id).where(ShopCredentialBinding.shop_id.in_(shop_ids))))',
    '        session.execute(delete(ShopSession).where(ShopSession.shop_id.in_(shop_ids)))',
    '        session.execute(delete(ShopCredentialBinding).where(ShopCredentialBinding.shop_id.in_(shop_ids)))',
    '        if credential_ids:',
    '            session.execute(delete(PlatformCredential).where(PlatformCredential.credential_id.in_(credential_ids)))',
    '        session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.shop_id.in_(shop_ids)))',
    '        session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))',
    '    if device_ids:',
    '        session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.device_id.in_(device_ids)))',
    '        session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))',
    '        session.execute(delete(DeviceProviderInventory).where(DeviceProviderInventory.device_id.in_(device_ids)))',
    '        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)))',
    '        session.execute(delete(WorkerDeviceCredential).where(WorkerDeviceCredential.device_id.in_(device_ids)))',
    '        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))',
    '    session.commit()',
  ].join('\n')

  execFileSync(backendPython, ['-c', cleanupScript], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
}

function issueWorkerIdentity(deviceName: string): {
  deviceId: string
  token: string
} {
  const issueScript = [
    'import json',
    'from sqlalchemy import select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.devices.models import Device',
    'from app.modules.workers.service import WorkerService',
    `device_name = ${JSON.stringify(deviceName)}`,
    'with Session(get_database_engine()) as session:',
    '    device = session.scalar(select(Device).where(Device.display_name == device_name))',
    '    assert device is not None',
    '    token = WorkerService(session).issue_token(device.device_id)',
    '    print(json.dumps({"deviceId": str(device.device_id), "token": token}))',
  ].join('\n')

  return JSON.parse(
    execFileSync(backendPython, ['-c', issueScript], {
      cwd: backendDirectory,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }),
  ) as { deviceId: string; token: string }
}

function reconcileDeviceOffline(secondsAfterHeartbeat: number): number {
  const reconcileScript = [
    'from datetime import UTC, datetime, timedelta',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.workers.service import WorkerService',
    `seconds = ${secondsAfterHeartbeat}`,
    'with Session(get_database_engine()) as session:',
    '    print(WorkerService(session).reconcile_offline_devices(now=datetime.now(UTC) + timedelta(seconds=seconds)))',
  ].join('\n')

  return Number(
    execFileSync(backendPython, ['-c', reconcileScript], {
      cwd: backendDirectory,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim(),
  )
}

function seedCapturedSession(shopId: string): void {
  const script = [
    'from datetime import UTC, datetime',
    'from uuid import UUID',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.core.security import get_secret_cipher',
    'from app.modules.sessions.enums import ShopSessionStatus',
    'from app.modules.sessions.schemas import StoreShopSessionCommand',
    'from app.modules.sessions.service import ShopSessionService',
    `shop_id = UUID(${JSON.stringify(shopId)})`,
    'with Session(get_database_engine()) as session:',
    '    ShopSessionService(session, get_secret_cipher()).store_payload(',
    '        StoreShopSessionCommand(shop_id=shop_id, expected_version=0, status=ShopSessionStatus.CAPTURED, source_device_id=None, captured_at=datetime.now(UTC)),',
    '        b"stage-shop-soft-delete-session",',
    '    )',
  ].join('\n')
  execFileSync(backendPython, ['-c', script], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
}

function inspectSoftRemovedShop(shopId: string, deviceId: string): {
  shopExists: boolean
  enabled: boolean
  deleted: boolean
  bindingEnabled: boolean
  credentialExists: boolean
  sessionExists: boolean
} {
  const script = [
    'import json',
    'from uuid import UUID',
    'from sqlalchemy import select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.credentials.models import ShopCredentialBinding',
    'from app.modules.sessions.models import ShopSession',
    'from app.modules.shops.models import Shop, ShopDeviceBinding',
    `shop_id = UUID(${JSON.stringify(shopId)})`,
    `device_id = UUID(${JSON.stringify(deviceId)})`,
    'with Session(get_database_engine()) as session:',
    '    shop = session.get(Shop, shop_id)',
    '    binding = session.get(ShopDeviceBinding, (shop_id, device_id))',
    '    credential_binding = session.scalar(select(ShopCredentialBinding).where(ShopCredentialBinding.shop_id == shop_id))',
    '    shop_session = session.scalar(select(ShopSession).where(ShopSession.shop_id == shop_id))',
    '    print(json.dumps({"shopExists": shop is not None, "enabled": bool(shop.enabled) if shop else False, "deleted": shop.deleted_at is not None if shop else False, "bindingEnabled": bool(binding.enabled) if binding else False, "credentialExists": credential_binding is not None, "sessionExists": shop_session is not None}))',
  ].join('\n')
  return JSON.parse(
    execFileSync(backendPython, ['-c', script], {
      cwd: backendDirectory,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }),
  )
}

function inspectSoftRemovedDevice(deviceId: string): {
  deviceExists: boolean
  enabled: boolean
  deleted: boolean
  bindingEnabled: boolean
  credentialEnabled: boolean
  taskExists: boolean
  runtimeExists: boolean
  inventoryExists: boolean
} {
  const script = [
    'import json',
    'from uuid import UUID',
    'from sqlalchemy import select',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.devices.models import Device',
    'from app.modules.shops.models import ShopDeviceBinding',
    'from app.modules.tasks.models import Task',
    'from app.modules.workers.models import DeviceProviderInventory, DeviceRuntime, WorkerDeviceCredential',
    `device_id = UUID(${JSON.stringify(deviceId)})`,
    'with Session(get_database_engine()) as session:',
    '    device = session.get(Device, device_id)',
    '    binding = session.scalar(select(ShopDeviceBinding).where(ShopDeviceBinding.device_id == device_id))',
    '    credential = session.scalar(select(WorkerDeviceCredential).where(WorkerDeviceCredential.device_id == device_id))',
    '    task = session.scalar(select(Task).where(Task.target_device_id == device_id))',
    '    runtime = session.get(DeviceRuntime, device_id)',
    '    inventory = session.scalar(select(DeviceProviderInventory).where(DeviceProviderInventory.device_id == device_id))',
    '    print(json.dumps({"deviceExists": device is not None, "enabled": bool(device.enabled) if device else False, "deleted": device.deleted_at is not None if device else False, "bindingEnabled": bool(binding.enabled) if binding else False, "credentialEnabled": bool(credential.enabled) if credential else False, "taskExists": task is not None, "runtimeExists": runtime is not None, "inventoryExists": inventory is not None}))',
  ].join('\n')
  return JSON.parse(
    execFileSync(backendPython, ['-c', script], {
      cwd: backendDirectory,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }),
  )
}

test.beforeAll(cleanupRealTestData)
test.afterAll(cleanupRealTestData)

test('persists shop and device records through FastAPI and PostgreSQL', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const runtimeErrors: string[] = []
  let collectRuntimeErrors = true
  page.on('console', (message) => {
    if (collectRuntimeErrors && message.type() === 'error') {
      runtimeErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    if (collectRuntimeErrors) runtimeErrors.push(error.message)
  })

  let delayInitialShops = true
  await page.route('**/api/v1/shops?page=*', async (route) => {
    if (delayInitialShops) {
      delayInitialShops = false
      await new Promise((resolve) => setTimeout(resolve, 600))
    }
    await route.continue()
  })
  await page.goto('/#/shops')
  await expect(page.getByText('正在加载，请稍候…')).toBeVisible()
  await expect(page.getByText('正在加载，请稍候…')).toHaveCount(0)
  await page.unroute('**/api/v1/shops?page=*')

  const shopName = `${testPrefix}shop`
  const updatedShopName = `${testPrefix}shop-updated`
  await page.getByRole('button', { name: '新增店铺' }).click()
  await expect(page.getByText('新增店铺', { exact: true })).toBeVisible()
  await expect(page.getByText('登录并识别', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  const createResponse = await page.request.post('/api/v1/shops', {
    data: { display_name: shopName, platform: 'douyin' },
  })
  expect(createResponse.ok()).toBe(true)
  await page.reload()
  await expect(page.getByText(shopName, { exact: true })).toBeVisible()

  await page.reload()
  await expect(page.getByText(shopName, { exact: true })).toBeVisible()
  await page
    .getByRole('row')
    .filter({ hasText: shopName })
    .getByRole('button', { name: '查看' })
    .click()
  await page.getByRole('button', { name: '编辑' }).click()
  await page.getByPlaceholder('请输入店铺名称').fill(updatedShopName)
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(updatedShopName, { exact: true })).toBeVisible()
  await page
    .getByRole('row')
    .filter({ hasText: updatedShopName })
    .getByRole('button', { name: '查看' })
    .click()
  await expect(page.getByRole('heading', { name: '账号与连接' })).toBeVisible()
  await expect(
    page.locator('.shop-session-card').getByText('未登录', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '配置账号与连接' }).click()
  await page
    .getByPlaceholder('手机号、邮箱、用户名或账号 ID')
    .fill('13812348888')
  await page.getByPlaceholder('请输入登录密码').fill('stage-3a-password')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(
    page.getByRole('row', { name: /登录账号/ }).getByText('138****8888'),
  ).toBeVisible()
  await expect(
    page.getByRole('row', { name: /登录密码/ }).getByText('已配置'),
  ).toBeVisible()
  await expect(page.getByText('stage-3a-password')).toHaveCount(0)
  await expect(page.getByText('登录会话', { exact: true })).toBeVisible()
  await expect(
    page.locator('.shop-session-card').getByText('未登录', { exact: true }),
  ).toBeVisible()

  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.reload()
  await page
    .getByRole('row')
    .filter({ hasText: updatedShopName })
    .getByRole('button', { name: '查看' })
    .click()
  await expect(
    page.getByRole('row', { name: /登录账号/ }).getByText('138****8888'),
  ).toBeVisible()
  await page.getByRole('button', { name: '更新账号与连接' }).click()
  await page.getByPlaceholder('留空保留当前登录账号').fill('account-updated')
  await expect(page.getByPlaceholder('留空表示不修改现有密码')).toHaveValue('')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(
    page.getByRole('row', { name: /登录账号/ }).getByText('ac***ed'),
  ).toBeVisible()

  await page.getByRole('button', { name: '更新账号与连接' }).click()
  await page.getByPlaceholder('留空表示不修改现有密码').fill('updated-password')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(
    page.getByRole('row', { name: /登录密码/ }).getByText('已配置'),
  ).toBeVisible()
  await expect(page.getByText('updated-password')).toHaveCount(0)
  await page.getByRole('button', { name: '关闭', exact: true }).click()

  await page.getByText('设备中心', { exact: true }).click()
  await expect(page.getByRole('button', { name: '添加设备' })).toBeVisible()
  const deviceName = `${testPrefix}device`
  const updatedDeviceName = `${testPrefix}device-updated`
  await page.getByRole('button', { name: '添加设备' }).click()
  await page.getByPlaceholder('请输入设备名称').fill(deviceName)
  await page.getByPlaceholder('请输入位置（选填）').fill('测试区')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(deviceName, { exact: true })).toBeVisible()

  await page.reload()
  await expect(page.getByText(deviceName, { exact: true })).toBeVisible()
  await page
    .getByRole('row')
    .filter({ hasText: deviceName })
    .getByRole('button', { name: '编辑' })
    .click()
  await page.getByPlaceholder('请输入设备名称').fill(updatedDeviceName)
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(updatedDeviceName, { exact: true })).toBeVisible()
  const workerIdentity = issueWorkerIdentity(updatedDeviceName)
  const inventoryResponse = await page.request.post(
    'http://127.0.0.1:8000/api/v1/worker/provider-inventory',
    {
      headers: {
        Authorization: `Bearer ${workerIdentity.token}`,
        'X-Device-ID': workerIdentity.deviceId,
      },
      data: {
        provider_code: 'yingdao',
        inventory: {
          provider: 'yingdao',
          available: true,
          status: 'ready',
          provider_version: '6.3.6',
          execution_available: true,
          execution_version: '6.3.6',
          logged_in: true,
          account_display: 'GY00999',
          account_type: 'PersonalBasic',
          enterprise_account: false,
          user_id: 'yingdao-user-e2e',
          applications: [
            {
              app_id: 'stage-3b-1a-app',
              app_name: '影刀应用 E2E',
              version_id: '1',
              updated_at: null,
              app_type: null,
              group_id: null,
            },
          ],
          discovered_at: new Date().toISOString(),
        },
      },
    },
  )
  expect(inventoryResponse.ok()).toBe(true)
  await page
    .getByRole('row')
    .filter({ hasText: updatedDeviceName })
    .getByRole('button', { name: '查看' })
    .click()
  const deviceDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: new RegExp(updatedDeviceName) }),
  })
  await expect(
    page.getByRole('heading', { name: new RegExp(updatedDeviceName) }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '执行能力' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '影刀 RPA' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '最近执行' })).toBeVisible()
  await expect(deviceDrawer.getByText('6.3.6', { exact: true })).toBeVisible()
  await expect(deviceDrawer.getByText('GY00999', { exact: true })).toBeVisible()
  await expect(
    deviceDrawer.getByText('PersonalBasic', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '查看应用' }).click()
  await expect(page.getByText('影刀应用列表', { exact: true })).toBeVisible()
  await expect(page.getByText('影刀应用 E2E', { exact: true })).toBeVisible()
  await expect(page.getByText('stage-3b-1a-app', { exact: true })).toBeVisible()
  const applicationsDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: '影刀应用列表' }),
  })
  await applicationsDrawer.getByRole('button', { name: '配置' }).click()
  const configDialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', {
      name: '配置参数 · 影刀应用 E2E',
    }),
  })
  await configDialog.getByRole('button', { name: '添加参数' }).click()
  await configDialog.getByPlaceholder('例如 product_id').fill('message')
  await configDialog.getByPlaceholder('例如 商品 ID').fill('测试消息')
  await configDialog.getByRole('button', { name: '保存' }).click()
  await expect(configDialog).toHaveCount(0)

  await applicationsDrawer.getByRole('button', { name: '运行' }).click()
  const runDialog = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: '运行应用 · 影刀应用 E2E' }),
  })
  await runDialog.getByRole('textbox').fill('hello')
  await runDialog.getByRole('button', { name: '运行', exact: true }).click()
  const runtimeDrawer = page.getByRole('dialog').filter({
    has: page.getByRole('heading', { name: '运行详情' }),
  })
  await expect(runtimeDrawer.getByText('yingdao.app.run')).toBeVisible()
  await runtimeDrawer.getByRole('button', { name: '关闭' }).click()
  await applicationsDrawer
    .getByRole('button', { name: '关闭', exact: true })
    .click()
  await expect(page.getByText('影刀应用列表', { exact: true })).toHaveCount(0)
  await deviceDrawer.getByRole('button', { name: '关闭', exact: true }).click()

  await page.getByText('店铺中心', { exact: true }).click()
  await page
    .getByRole('row')
    .filter({ hasText: updatedShopName })
    .getByRole('button', { name: '查看' })
    .click()
  await page.getByRole('button', { name: '绑定设备', exact: true }).click()
  await page.getByRole('dialog').last().getByRole('textbox').click()
  await page
    .locator('.n-base-select-option')
    .filter({ hasText: updatedDeviceName })
    .click()
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(updatedDeviceName).last()).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()

  await page.reload()
  await page
    .getByRole('row')
    .filter({ hasText: updatedShopName })
    .getByRole('button', { name: '查看' })
    .click()
  await expect(page.getByText(updatedDeviceName).last()).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByText('设备中心', { exact: true }).click()

  const layout = await page.evaluate(() => ({
    documentHasHorizontalOverflow:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    bodyHasHorizontalOverflow:
      document.body.scrollWidth > document.body.clientWidth,
  }))
  expect(layout.documentHasHorizontalOverflow).toBe(false)
  expect(layout.bodyHasHorizontalOverflow).toBe(false)
  expect(runtimeErrors).toEqual([])

  collectRuntimeErrors = false
  await page.route('**/api/v1/devices?page=*', (route) => route.abort())
  await page.reload()
  await expect(page.getByText('无法连接到服务')).toBeVisible()
  await page.unroute('**/api/v1/devices?page=*')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByText(updatedDeviceName, { exact: true })).toBeVisible()
})

test('validates the real HuanYu session and restores its enabled state', async ({
  page,
}) => {
  test.setTimeout(60_000)
  await page.goto('/#/shops')
  const row = page.getByRole('row').filter({ hasText: 'HuanYu' })
  await expect(row.getByText('有效', { exact: true })).toBeVisible()
  const listPayload = await (await page.request.get('/api/v1/shops?page=1&page_size=100')).json()
  const huanyu = listPayload.items.find(
    (shop: { display_name: string }) => shop.display_name === 'HuanYu',
  ) as { shop_id: string; enabled: boolean }
  expect(huanyu.enabled).toBe(true)

  const before = await (
    await page.request.get(`/api/v1/shops/${huanyu.shop_id}/session`)
  ).json()
  await row.getByRole('button', { name: '查看' }).click()
  const healthResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/shops/${huanyu.shop_id}/session/health-check`) &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '验证会话' }).click()
  expect((await healthResponse).ok()).toBe(true)
  await expect(page.locator('.shop-session-card').getByText('有效')).toBeVisible()
  const after = await (
    await page.request.get(`/api/v1/shops/${huanyu.shop_id}/session`)
  ).json()
  expect(new Date(after.validated_at).getTime()).toBeGreaterThan(
    new Date(before.validated_at).getTime(),
  )
  await page.getByRole('button', { name: '关闭', exact: true }).click()

  try {
    await row.getByRole('button', { name: '停用', exact: true }).click()
    await page.reload()
    let refreshedRow = page.getByRole('row').filter({ hasText: 'HuanYu' })
    await expect(refreshedRow.getByText('已停用', { exact: true })).toBeVisible()
    await refreshedRow.getByRole('button', { name: '启用', exact: true }).click()
    await page.reload()
    refreshedRow = page.getByRole('row').filter({ hasText: 'HuanYu' })
    await expect(refreshedRow.getByText('已启用', { exact: true })).toBeVisible()
  } finally {
    await page.request.patch(`/api/v1/shops/${huanyu.shop_id}`, {
      data: { enabled: true },
    })
  }
})

test('persists Shop.enabled and safely soft-removes a dedicated real Shop', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const shopName = `${testPrefix}soft-remove-shop`
  const deviceName = `${testPrefix}soft-remove-device`
  const shopResponse = await page.request.post('/api/v1/shops', {
    data: { display_name: shopName, platform: 'douyin' },
  })
  expect(shopResponse.ok()).toBe(true)
  const shopId = (await shopResponse.json()).shop_id as string
  const deviceResponse = await page.request.post('/api/v1/devices', {
    data: { display_name: deviceName },
  })
  expect(deviceResponse.ok()).toBe(true)
  const deviceId = (await deviceResponse.json()).device_id as string
  expect(
    (
      await page.request.post(`/api/v1/shops/${shopId}/device-bindings`, {
        data: { device_id: deviceId, binding_role: 'primary' },
      })
    ).ok(),
  ).toBe(true)
  expect(
    (
      await page.request.post('/api/v1/credentials', {
        data: {
          shop_id: shopId,
          login_identifier: 'stage-soft-remove-account',
          secret: 'stage-soft-remove-password',
        },
      })
    ).ok(),
  ).toBe(true)
  seedCapturedSession(shopId)

  await page.goto('/#/shops')
  let row = page.getByRole('row').filter({ hasText: shopName })
  await expect(row.getByText('待验证', { exact: true })).toBeVisible()
  await row.getByRole('button', { name: '停用', exact: true }).click()
  await expect(row.getByText('已停用', { exact: true })).toBeVisible()
  await page.reload()
  row = page.getByRole('row').filter({ hasText: shopName })
  await expect(row.getByText('已停用', { exact: true })).toBeVisible()
  await row.getByRole('button', { name: '启用', exact: true }).click()
  await page.reload()
  row = page.getByRole('row').filter({ hasText: shopName })
  await expect(row.getByText('已启用', { exact: true })).toBeVisible()

  await row.getByRole('button', { name: '移除', exact: true }).click()
  await page.getByRole('button', { name: '确认移除' }).click()
  await expect(page.getByText(shopName, { exact: true })).toHaveCount(0)
  const detailResponse = await page.request.get(`/api/v1/shops/${shopId}`)
  expect(detailResponse.status()).toBe(404)
  expect(await detailResponse.json()).toMatchObject({ code: 'SHOP_NOT_FOUND' })

  expect(inspectSoftRemovedShop(shopId, deviceId)).toEqual({
    shopExists: true,
    enabled: false,
    deleted: true,
    bindingEnabled: false,
    credentialExists: true,
    sessionExists: true,
  })
})

test('protects active Device tasks and revokes every Worker endpoint after soft removal', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const deviceName = `${testPrefix}device-lifecycle`
  const shopName = `${testPrefix}device-lifecycle-shop`
  const deviceResponse = await page.request.post('/api/v1/devices', {
    data: { display_name: deviceName },
  })
  const shopResponse = await page.request.post('/api/v1/shops', {
    data: { display_name: shopName, platform: 'douyin' },
  })
  expect(deviceResponse.ok()).toBe(true)
  expect(shopResponse.ok()).toBe(true)
  const deviceId = (await deviceResponse.json()).device_id as string
  const shopId = (await shopResponse.json()).shop_id as string
  expect(
    (
      await page.request.post(`/api/v1/shops/${shopId}/device-bindings`, {
        data: { device_id: deviceId, binding_role: 'primary' },
      })
    ).ok(),
  ).toBe(true)
  const identity = issueWorkerIdentity(deviceName)
  const workerHeaders = {
    Authorization: `Bearer ${identity.token}`,
    'X-Device-ID': identity.deviceId,
  }
  const now = new Date().toISOString()
  expect(
    (
      await page.request.post('/api/v1/worker/heartbeat', {
        headers: workerHeaders,
        data: { worker_version: '0.1.0', started_at: now },
      })
    ).ok(),
  ).toBe(true)
  const inventoryPayload = {
    provider_code: 'yingdao',
    inventory: {
      provider: 'yingdao',
      available: true,
      status: 'ready',
      provider_version: '6.3.6',
      execution_available: true,
      execution_version: '6.3.6',
      logged_in: true,
      account_display: 'E2E',
      account_type: 'PersonalBasic',
      enterprise_account: false,
      user_id: 'device-lifecycle-e2e',
      applications: [],
      discovered_at: now,
    },
  }
  expect(
    (
      await page.request.post('/api/v1/worker/provider-inventory', {
        headers: workerHeaders,
        data: inventoryPayload,
      })
    ).ok(),
  ).toBe(true)
  const taskResponse = await page.request.post('/api/v1/tasks', {
    data: {
      target_device_id: deviceId,
      skill_id: 'system.echo',
      input: { message: 'device lifecycle e2e' },
    },
  })
  expect(taskResponse.ok()).toBe(true)

  const protectedRemove = await page.request.delete(`/api/v1/devices/${deviceId}`)
  expect(protectedRemove.status()).toBe(409)
  expect(await protectedRemove.json()).toMatchObject({
    code: 'DEVICE_HAS_ACTIVE_TASKS',
  })

  const claimed = await page.request.post('/api/v1/worker/tasks/claim', {
    headers: workerHeaders,
  })
  expect(claimed.ok()).toBe(true)
  const taskId = (await claimed.json()).task_id as string
  expect(
    (
      await page.request.post(`/api/v1/worker/tasks/${taskId}/complete`, {
        headers: workerHeaders,
        data: { result: { ok: true } },
      })
    ).ok(),
  ).toBe(true)

  await page.goto('/#/devices')
  const row = page.getByRole('row').filter({ hasText: deviceName })
  await row.getByRole('button', { name: '移除' }).click()
  await page.getByRole('button', { name: '确认移除' }).click()
  await expect(page.getByText(deviceName, { exact: true })).toHaveCount(0)

  for (const request of [
    page.request.post('/api/v1/worker/heartbeat', {
      headers: workerHeaders,
      data: { worker_version: '0.1.0', started_at: now },
    }),
    page.request.post('/api/v1/worker/tasks/claim', { headers: workerHeaders }),
    page.request.post('/api/v1/worker/provider-inventory', {
      headers: workerHeaders,
      data: inventoryPayload,
    }),
  ]) {
    expect((await request).status()).toBe(401)
  }
  expect(inspectSoftRemovedDevice(deviceId)).toEqual({
    deviceExists: true,
    enabled: false,
    deleted: true,
    bindingEnabled: false,
    credentialEnabled: false,
    taskExists: true,
    runtimeExists: true,
    inventoryExists: true,
  })
  const replacement = await page.request.post('/api/v1/devices', {
    data: { display_name: deviceName },
  })
  expect(replacement.ok()).toBe(true)
  expect((await replacement.json()).device_id).not.toBe(deviceId)
})

test('keeps the same Device row through ONLINE, OFFLINE and ONLINE recovery', async ({
  page,
}) => {
  const deviceName = `${testPrefix}offline-list`
  const createResponse = await page.request.post('/api/v1/devices', {
    data: { display_name: deviceName },
  })
  expect(createResponse.status()).toBe(201)
  const identity = issueWorkerIdentity(deviceName)
  const workerHeaders = {
    Authorization: `Bearer ${identity.token}`,
    'X-Device-ID': identity.deviceId,
  }
  const startedAt = new Date().toISOString()

  expect(
    (
      await page.request.post('/api/v1/worker/heartbeat', {
        headers: workerHeaders,
        data: { worker_version: '0.1.0', started_at: startedAt },
      })
    ).status(),
  ).toBe(200)

  await page.goto('/#/devices')
  let row = page.getByRole('row').filter({ hasText: deviceName })
  await expect(row.getByText('在线', { exact: true })).toBeVisible()

  expect(reconcileDeviceOffline(46)).toBeGreaterThanOrEqual(1)
  expect(reconcileDeviceOffline(60)).toBe(0)
  await page.reload()
  row = page.getByRole('row').filter({ hasText: deviceName })
  await expect(row.getByText('离线', { exact: true })).toBeVisible()
  await expect(row.getByText('—', { exact: true }).first()).toBeVisible()
  await expect(row).not.toContainText('未接入')
  await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)

  await page.route('**/api/v1/devices?**', (route) => route.abort())
  const failedRefresh = page.waitForEvent(
    'requestfailed',
    (request) =>
      request.url().includes('/api/v1/devices?') &&
      request.method() === 'GET',
  )
  await page.getByRole('button', { name: '刷新' }).click()
  await failedRefresh
  await expect(row).toBeVisible()
  await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)
  await page.unroute('**/api/v1/devices?**')

  expect(
    (
      await page.request.post('/api/v1/worker/heartbeat', {
        headers: workerHeaders,
        data: { worker_version: '0.1.0', started_at: startedAt },
      })
    ).status(),
  ).toBe(200)
  await page.reload()
  row = page.getByRole('row').filter({ hasText: deviceName })
  await expect(row.getByText('在线', { exact: true })).toBeVisible()
  await expect(page.getByText(deviceName, { exact: true })).toHaveCount(1)
})
