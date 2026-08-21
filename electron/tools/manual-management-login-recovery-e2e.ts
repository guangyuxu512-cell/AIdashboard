import { app, BrowserWindow } from 'electron'
import path from 'node:path'

import { ManagementLoginService } from '../services'

interface ShopPage {
  items: Array<{
    shop_id: string
    display_name: string
    platform: 'douyin' | 'pdd'
    platform_shop_id: string | null
  }>
}

interface RefreshLease {
  lease_id: string
  expected_version: number
}

const configuredBackend =
  process.env.CONTROL_CENTER_BACKEND_URL || 'http://127.0.0.1:8000'
const service = new ManagementLoginService()

app.setPath(
  'userData',
  path.join(app.getPath('appData'), '@control-center', 'electron'),
)

void app.whenReady().then(async () => {
  const parent = new BrowserWindow({
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  try {
    const shops = await requestJson<ShopPage>('/api/v1/shops?page=1&page_size=100')
    const shop = shops.items.find(
      (item) => item.display_name === 'HuanYu' && item.platform === 'douyin',
    )
    if (!shop) throw new Error('HuanYu shop not found')
    const lease = await requestJson<RefreshLease>(
      `/api/v1/shops/${shop.shop_id}/session/refresh-lease`,
      { method: 'POST' },
    )
    let status = await service.open(parent, {
      platform: 'douyin',
      recovery: {
        shopId: shop.shop_id,
        leaseId: lease.lease_id,
        expectedVersion: lease.expected_version,
      },
    })
    for (let attempt = 0; attempt < 120 && status.status === 'waiting'; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      status = await service.getStatus(status.attemptId)
    }
    if (status.status !== 'identified') {
      throw new Error(`profile recapture did not identify: ${status.status}`)
    }
    const result = await service.refresh(status.attemptId)
    process.stdout.write(
      `${JSON.stringify({
        shop: 'HuanYu',
        profile_reused: status.profileReused,
        identity_matches:
          status.identity?.platformShopId === shop.platform_shop_id,
        session_status: result.status,
        session_version: result.sessionVersion,
        cookie_updates_applied: result.cookieUpdatesApplied,
      })}\n`,
    )
  } catch (error) {
    process.stderr.write(
      `${error instanceof Error ? error.message : 'recovery e2e failed'}\n`,
    )
    process.exitCode = 1
  } finally {
    await service.closeAll()
    parent.destroy()
    app.quit()
  }
})

async function requestJson<T>(
  pathname: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(new URL(pathname, configuredBackend), init)
  if (!response.ok) throw new Error(`Backend HTTP ${response.status}`)
  return (await response.json()) as T
}
