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
    'from app.modules.devices.models import Device',
    'from app.modules.shops.models import Shop, ShopDeviceBinding',
    `prefix = ${JSON.stringify(`${testPrefix}%`)}`,
    'with Session(get_database_engine()) as session:',
    '    shop_ids = list(session.scalars(select(Shop.shop_id).where(Shop.display_name.like(prefix))))',
    '    device_ids = list(session.scalars(select(Device.device_id).where(Device.display_name.like(prefix))))',
    '    if shop_ids:',
    '        session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.shop_id.in_(shop_ids)))',
    '        session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))',
    '    if device_ids:',
    '        session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.device_id.in_(device_ids)))',
    '        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))',
    '    session.commit()',
  ].join('\n')

  execFileSync(backendPython, ['-c', cleanupScript], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
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
  await page.getByPlaceholder('请输入店铺名称').fill(shopName)
  await expect(page.getByText('抖店', { exact: true }).last()).toBeVisible()
  const createDialog = page.locator('.n-modal')
  await createDialog.getByText('抖店', { exact: true }).click()
  const platformOptions = page.locator('.n-base-select-option')
  await expect(platformOptions.filter({ hasText: '淘宝' })).toHaveClass(
    /--disabled/,
  )
  await expect(platformOptions.filter({ hasText: '视频号' })).toHaveClass(
    /--disabled/,
  )
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(shopName, { exact: true })).toBeVisible()
  await expect(
    page
      .getByRole('row')
      .filter({ hasText: shopName })
      .getByRole('checkbox'),
  ).toBeChecked()

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
  await expect(
    page.getByRole('heading', { name: '账号与连接' }),
  ).toBeVisible()
  await expect(page.getByText('未配置')).toBeVisible()
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
  await page
    .getByRole('row')
    .filter({ hasText: updatedDeviceName })
    .getByRole('button', { name: '查看' })
    .click()
  await expect(page.getByText('设备详情', { exact: true })).toBeVisible()
  await expect(page.getByText('Worker 执行能力尚未接入')).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()

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
