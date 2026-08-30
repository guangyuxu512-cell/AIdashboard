import type { PageDto } from '@/shared/api'

import type {
  DeviceProviderInventoryReadDto,
  DeviceReadDto,
  DeviceSkillCapabilityReadDto,
  YingdaoProviderStatusDto,
} from './contracts'
import type { DeviceDataSource } from './device-api'

export const VISUAL_DEVICE_IDS = {
  operations: 'visual-device-operations',
  support: 'visual-device-support',
  marketing: 'visual-device-marketing',
  service: 'visual-device-service',
  data: 'visual-device-data',
} as const

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

function createRuntime(
  deviceId: string,
  workerVersion: string,
  connectionStatus: 'online' | 'offline',
  lastSeenMinutesAgo: number,
) {
  return {
    device_id: deviceId,
    worker_version: workerVersion,
    connection_status: connectionStatus,
    last_seen_at: minutesAgo(lastSeenMinutesAgo),
    started_at: minutesAgo(240),
    updated_at: minutesAgo(lastSeenMinutesAgo),
  } as const
}

export function createVisualDeviceDtos(): DeviceReadDto[] {
  const createdAt = minutesAgo(30 * 24 * 60)
  const primaryDevices: DeviceReadDto[] = [
    {
      device_id: VISUAL_DEVICE_IDS.operations,
      display_name: '运营',
      enabled: true,
      location: '华东运营组',
      note: '订单自动化主设备',
      deleted_at: null,
      worker_runtime: createRuntime(
        VISUAL_DEVICE_IDS.operations,
        '0.4.6',
        'online',
        0,
      ),
      created_at: createdAt,
      updated_at: minutesAgo(0),
    },
    {
      device_id: VISUAL_DEVICE_IDS.support,
      display_name: '售后',
      enabled: true,
      location: '售后服务组',
      note: null,
      deleted_at: null,
      worker_runtime: createRuntime(
        VISUAL_DEVICE_IDS.support,
        '0.4.6',
        'online',
        0,
      ),
      created_at: createdAt,
      updated_at: minutesAgo(1),
    },
    {
      device_id: VISUAL_DEVICE_IDS.marketing,
      display_name: '营销',
      enabled: false,
      location: '内容营销组',
      note: '暂时停用',
      deleted_at: null,
      worker_runtime: createRuntime(
        VISUAL_DEVICE_IDS.marketing,
        '0.4.3',
        'online',
        1,
      ),
      created_at: createdAt,
      updated_at: minutesAgo(68),
    },
    {
      device_id: VISUAL_DEVICE_IDS.service,
      display_name: '客服自动化工作站（华东售后协同中心）',
      enabled: false,
      location: '客服一组',
      note: null,
      deleted_at: null,
      worker_runtime: createRuntime(
        VISUAL_DEVICE_IDS.service,
        '0.4.6',
        'offline',
        68,
      ),
      created_at: createdAt,
      updated_at: minutesAgo(3),
    },
    {
      device_id: VISUAL_DEVICE_IDS.data,
      display_name: '数据中心',
      enabled: false,
      location: null,
      note: null,
      deleted_at: null,
      worker_runtime: createRuntime(
        VISUAL_DEVICE_IDS.data,
        '0.4.5',
        'offline',
        120,
      ),
      created_at: createdAt,
      updated_at: minutesAgo(120),
    },
  ]

  const additionalDeviceNames = [
    '仓储一组',
    '商品组',
    '直播组',
    '订单组',
    '审核组',
    '采购组',
    '财务组',
    '内容组',
    '渠道组',
    '客服二组',
    '售后三组',
    '营销二组',
    '数据二组',
    '运营二组',
    '库存组',
  ]
  const additionalDevices = additionalDeviceNames.map<DeviceReadDto>(
    (displayName, index) => {
      const deviceId = `visual-device-${index + 6}`
      return {
        device_id: deviceId,
        display_name: displayName,
        enabled: true,
        location: null,
        note: null,
        deleted_at: null,
        worker_runtime: createRuntime(
          deviceId,
          index % 4 === 0 ? '0.4.6' : '0.4.5',
          index % 3 === 0 ? 'online' : 'offline',
          index + 2,
        ),
        created_at: createdAt,
        updated_at: minutesAgo(index + 2),
      }
    },
  )

  return [...primaryDevices, ...additionalDevices]
}

function providerStatus(deviceId: string): YingdaoProviderStatusDto | null {
  if (deviceId === VISUAL_DEVICE_IDS.operations) return 'ready'
  if (deviceId === VISUAL_DEVICE_IDS.support) return 'ready'
  if (deviceId === VISUAL_DEVICE_IDS.marketing) return 'interface_unreachable'
  if (deviceId === VISUAL_DEVICE_IDS.service) return 'starting'
  return null
}

function createProviderInventories(
  deviceId: string,
): DeviceProviderInventoryReadDto[] {
  const status = providerStatus(deviceId)
  if (!status) return []

  const ready = status === 'ready'
  const loggedIn = ready || status === 'starting'
  const available = status !== 'interface_unreachable'
  const discoveredAt = minutesAgo(2)
  return [
    {
      device_id: deviceId,
      provider_code: 'yingdao',
      available,
      provider_version: '6.3.6',
      account_display: loggedIn ? 'HuanYu001' : null,
      account_type: loggedIn ? 'enterprise' : null,
      enterprise_account: loggedIn ? true : null,
      last_discovered_at: discoveredAt,
      inventory: {
        provider: 'yingdao',
        available,
        status,
        status_reason_code: null,
        status_reason: null,
        provider_version: '6.3.6',
        execution_available: ready,
        execution_version: ready ? '6.3.6' : null,
        execution_unavailable_reason: null,
        logged_in: loggedIn,
        account_display: loggedIn ? 'HuanYu001' : null,
        account_type: loggedIn ? 'enterprise' : null,
        enterprise_account: loggedIn ? true : null,
        user_id: loggedIn ? 'visual-user-001' : null,
        applications: ready
          ? [
              {
                app_id: 'visual-app-orders',
                app_name: '拼多多自动处理售后退款与工单协同流程',
                version_id: '2026.08',
                updated_at: minutesAgo(120),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-publish',
                app_name: '商品发布',
                version_id: '2026.07',
                updated_at: minutesAgo(180),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-audit',
                app_name: '审核查询',
                version_id: '2026.07',
                updated_at: minutesAgo(190),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-marketing',
                app_name: '营销报名',
                version_id: '2026.06',
                updated_at: minutesAgo(200),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-sync-orders',
                app_name: '订单同步',
                version_id: '2026.06',
                updated_at: minutesAgo(210),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-service',
                app_name: '售后处理',
                version_id: '2026.05',
                updated_at: minutesAgo(220),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-edit',
                app_name: '商品编辑',
                version_id: '2026.05',
                updated_at: minutesAgo(230),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
              {
                app_id: 'visual-app-inventory',
                app_name: '库存同步',
                version_id: '2026.04',
                updated_at: minutesAgo(240),
                app_type: 'rpa',
                group_id: 'visual-group-commerce',
              },
            ]
          : [],
        discovered_at: discoveredAt,
      },
      updated_at: discoveredAt,
    },
  ]
}

function createSkillCapabilities(
  deviceId: string,
): DeviceSkillCapabilityReadDto[] {
  if (deviceId === VISUAL_DEVICE_IDS.data) return []
  const updatedAt = minutesAgo(4)
  const baseCapabilities: DeviceSkillCapabilityReadDto[] = [
    {
      device_id: deviceId,
      skill_id: 'visual-sync-orders',
      display_name: '订单同步',
      runtime: 'python',
      provider: null,
      version: '1.3.0',
      classification: 'business',
      input_schema: { type: 'object' },
      updated_at: updatedAt,
    },
    {
      device_id: deviceId,
      skill_id: 'visual-health-check',
      display_name: '运行状态检查',
      runtime: 'python',
      provider: null,
      version: '1.1.0',
      classification: 'internal',
      input_schema: null,
      updated_at: updatedAt,
    },
  ]

  if (deviceId !== VISUAL_DEVICE_IDS.operations) return baseCapabilities

  return [
    baseCapabilities[0]!,
    {
      device_id: deviceId,
      skill_id: 'visual-after-sale',
      display_name: '售后工单处理',
      runtime: 'python',
      provider: null,
      version: '1.2.0',
      classification: 'business',
      input_schema: { type: 'object' },
      updated_at: updatedAt,
    },
    {
      device_id: deviceId,
      skill_id: 'visual-product-publish',
      display_name: '商品发布',
      runtime: 'python',
      provider: null,
      version: '1.1.0',
      classification: 'business',
      input_schema: { type: 'object' },
      updated_at: updatedAt,
    },
    {
      device_id: deviceId,
      skill_id: 'visual-marketing-entry',
      display_name: '营销活动报名',
      runtime: 'python',
      provider: null,
      version: '1.0.0',
      classification: 'business',
      input_schema: null,
      updated_at: updatedAt,
    },
    {
      device_id: deviceId,
      skill_id: 'visual-inventory-sync',
      display_name: '库存同步',
      runtime: 'python',
      provider: null,
      version: '1.0.0',
      classification: 'business',
      input_schema: null,
      updated_at: updatedAt,
    },
    baseCapabilities[1]!,
    {
      device_id: deviceId,
      skill_id: 'visual-provider-discovery',
      display_name: '提供方发现',
      runtime: 'discovery',
      provider: 'yingdao',
      version: '1.0.0',
      classification: 'internal',
      input_schema: null,
      updated_at: updatedAt,
    },
  ]
}

function requireVisualDevice(deviceId: string): DeviceReadDto {
  const device = createVisualDeviceDtos().find(
    (candidate) => candidate.device_id === deviceId,
  )
  if (!device) throw new Error('Visual device fixture not found')
  return device
}

export const visualMockDeviceDataSource: DeviceDataSource = {
  async getDevices(params): Promise<PageDto<DeviceReadDto>> {
    const devices = createVisualDeviceDtos()
    const start = (params.page - 1) * params.page_size
    return {
      items: devices.slice(start, start + params.page_size),
      total: devices.length,
      page: params.page,
      page_size: params.page_size,
    }
  },
  async getDevice(deviceId) {
    return requireVisualDevice(deviceId)
  },
  async getDeviceProviderInventories(deviceId) {
    requireVisualDevice(deviceId)
    return createProviderInventories(deviceId)
  },
  async getDeviceSkillCapabilities(deviceId) {
    requireVisualDevice(deviceId)
    return createSkillCapabilities(deviceId)
  },
}
