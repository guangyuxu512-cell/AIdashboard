import dayjs from 'dayjs'

import { deviceApi } from '@/entities/device'
import { apiMode, type ApiMode } from '@/shared/api'

import type { ShopSessionMetadataViewModel } from '../model/types'
import { shopSessionApi } from './session-api'

export interface ShopSessionDataSource {
  readonly mode: ApiMode
  getForShop(shopId: string): Promise<ShopSessionMetadataViewModel>
}

function formatOptionalDate(value: string | null): string | null {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : null
}

const notConfiguredSession: ShopSessionMetadataViewModel = {
  sessionId: null,
  configured: false,
  status: 'not_configured',
  version: 0,
  sourceDeviceId: null,
  sourceDeviceName: null,
  capturedAtDisplay: null,
  validatedAtDisplay: null,
  expiresAtDisplay: null,
}

export function createMockShopSessionDataSource(): ShopSessionDataSource {
  return {
    mode: 'mock',
    async getForShop() {
      return { ...notConfiguredSession }
    },
  }
}

const realShopSessionDataSource: ShopSessionDataSource = {
  mode: 'real',
  async getForShop(shopId) {
    const session = await shopSessionApi.getForShop(shopId)
    let sourceDeviceName: string | null = null
    if (session.source_device_id) {
      const devices = await deviceApi.list({ page: 1, pageSize: 100 })
      sourceDeviceName =
        devices.items.find(
          (device) => device.device_id === session.source_device_id,
        )?.display_name ?? '未知设备'
    }
    return {
      sessionId: session.session_id,
      configured: session.configured,
      status: session.status,
      version: session.version,
      sourceDeviceId: session.source_device_id,
      sourceDeviceName,
      capturedAtDisplay: formatOptionalDate(session.captured_at),
      validatedAtDisplay: formatOptionalDate(session.validated_at),
      expiresAtDisplay: formatOptionalDate(session.expires_at),
    }
  },
}

export function createShopSessionDataSource(
  mode: ApiMode,
): ShopSessionDataSource {
  return mode === 'real'
    ? realShopSessionDataSource
    : createMockShopSessionDataSource()
}

export const shopSessionDataSource = createShopSessionDataSource(apiMode)
