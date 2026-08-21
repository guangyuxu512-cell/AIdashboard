import dayjs from 'dayjs'

import { deviceApi } from '@/entities/device'
import { apiMode, type ApiMode } from '@/shared/api'

import type {
  ShopSessionMetadataViewModel,
  ShopSessionRefreshLeaseViewModel,
} from '../model/types'
import { shopSessionApi } from './session-api'

export interface ShopSessionDataSource {
  readonly mode: ApiMode
  getForShop(shopId: string): Promise<ShopSessionMetadataViewModel>
  validate(shopId: string): Promise<void>
  acquireRefreshLease(shopId: string): Promise<ShopSessionRefreshLeaseViewModel>
  releaseRefreshLease(shopId: string, leaseId: string): Promise<void>
  confirmRecovery(
    shopId: string,
    version: number,
    validatedAt: string,
  ): Promise<void>
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
  refreshInProgress: false,
  refreshLeaseExpiresAtDisplay: null,
}

export function createMockShopSessionDataSource(): ShopSessionDataSource {
  const sessions = new Map<string, ShopSessionMetadataViewModel>()
  const getSession = (shopId: string): ShopSessionMetadataViewModel => {
    const existing = sessions.get(shopId)
    if (existing) return existing
    const initial =
      shopId === 'shop-fixture-001' || shopId === 'shop-fixture-003'
        ? {
            ...notConfiguredSession,
            sessionId: 'session-fixture-001',
            configured: true,
            status: 'invalid' as const,
            version: 3,
            capturedAtDisplay: '2026-08-21 21:30',
            validatedAtDisplay: '2026-08-21 22:00',
          }
        : { ...notConfiguredSession }
    sessions.set(shopId, initial)
    return initial
  }
  return {
    mode: 'mock',
    async getForShop(shopId) {
      return { ...getSession(shopId) }
    },
    async validate(shopId) {
      const current = getSession(shopId)
      sessions.set(shopId, {
        ...current,
        status: 'valid',
        validatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      })
    },
    async acquireRefreshLease(shopId) {
      if (shopId === 'shop-fixture-003') {
        throw new Error('该店铺登录会话正在恢复')
      }
      return {
        shopId,
        leaseId: crypto.randomUUID(),
        expectedVersion: 1,
        expiresAt: dayjs().add(30, 'minute').toISOString(),
      }
    },
    async releaseRefreshLease() {},
    async confirmRecovery(shopId, version, validatedAt) {
      const current = getSession(shopId)
      sessions.set(shopId, {
        ...current,
        status: 'valid',
        version,
        capturedAtDisplay: dayjs(validatedAt).format('YYYY-MM-DD HH:mm'),
        validatedAtDisplay: dayjs(validatedAt).format('YYYY-MM-DD HH:mm'),
      })
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
      refreshInProgress: session.refresh_in_progress,
      refreshLeaseExpiresAtDisplay: formatOptionalDate(
        session.refresh_lease_expires_at,
      ),
    }
  },
  async validate(shopId) {
    await shopSessionApi.validate(shopId)
  },
  async acquireRefreshLease(shopId) {
    const lease = await shopSessionApi.acquireRefreshLease(shopId)
    return {
      shopId: lease.shop_id,
      leaseId: lease.lease_id,
      expectedVersion: lease.expected_version,
      expiresAt: lease.expires_at,
    }
  },
  async releaseRefreshLease(shopId, leaseId) {
    await shopSessionApi.releaseRefreshLease(shopId, leaseId)
  },
  async confirmRecovery() {},
}

export function createShopSessionDataSource(
  mode: ApiMode,
): ShopSessionDataSource {
  return mode === 'real'
    ? realShopSessionDataSource
    : createMockShopSessionDataSource()
}

export const shopSessionDataSource = createShopSessionDataSource(apiMode)
