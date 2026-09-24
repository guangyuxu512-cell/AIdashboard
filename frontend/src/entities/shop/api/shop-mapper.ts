import dayjs from 'dayjs'

import type { DeviceReadDto } from '@/entities/device'
import type { UserReadDto } from '@/entities/user'

import type { ShopListItemViewModel, ShopSaveInput } from '../model/types'
import type {
  BackendShopPlatform,
  ShopCreateDto,
  ShopDeviceBindingReadDto,
  ShopListReadDto,
  ShopReadDto,
  ShopUpdateDto,
} from './contracts'

export interface ShopMappingContext {
  users: UserReadDto[]
  devices: DeviceReadDto[]
  bindings: ShopDeviceBindingReadDto[]
}

function formatDateTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function mapShopDto(
  dto: ShopReadDto | ShopListReadDto,
  context: ShopMappingContext,
): ShopListItemViewModel {
  const owner = context.users.find((user) => user.user_id === dto.owner_user_id)
  const deviceNames = new Map(
    context.devices.map((device) => [device.device_id, device.display_name]),
  )
  const activeBindings = context.bindings.filter((binding) => binding.enabled)
  const deviceBindings = context.bindings.map((binding) => ({
    deviceId: binding.device_id,
    deviceName: deviceNames.get(binding.device_id) ?? '未知设备',
    enabled: binding.enabled,
  }))

  return {
    shopId: dto.shop_id,
    shopName: dto.display_name,
    platform: dto.platform,
    platformShopId: dto.platform_shop_id,
    ownerUserId: dto.owner_user_id,
    ownerName: dto.owner_user_id
      ? (owner?.display_name ?? '未知用户')
      : '未分配',
    enabled: dto.enabled,
    enabledStatus: dto.enabled ? 'enabled' : 'disabled',
    loginStatus: 'session_status' in dto
      ? (dto.session_status ?? 'not_configured')
      : 'not_configured',
    executionDeviceIds: activeBindings.map((binding) => binding.device_id),
    executionDeviceNames: activeBindings.map(
      (binding) => deviceNames.get(binding.device_id) ?? '未知设备',
    ),
    deviceBindings,
    createdAtDisplay: formatDateTime(dto.created_at),
    updatedAtDisplay: formatDateTime(dto.updated_at),
    note: dto.note || '',
    operatingStartDate: dto.operating_start_date ?? null,
    dataSource: 'real',
  }
}

function requireBackendPlatform(platform: string): BackendShopPlatform {
  if (platform === 'douyin' || platform === 'pdd') return platform
  throw new Error('真实 API 当前只支持抖音和拼多多平台')
}

export function mapShopCreateInput(input: ShopSaveInput): ShopCreateDto {
  return {
    display_name: input.shopName.trim(),
    platform: requireBackendPlatform(input.platform),
    enabled: input.enabled,
    owner_user_id: input.ownerUserId,
    note: input.note.trim() || null,
  }
}

export function mapShopUpdateInput(input: ShopSaveInput): ShopUpdateDto {
  const editableFields: ShopUpdateDto = {
    enabled: input.enabled,
    owner_user_id: input.ownerUserId,
    note: input.note.trim() || null,
  }
  if (input.operatingStartDate !== undefined) {
    editableFields.operating_start_date = input.operatingStartDate
  }
  if (!input.platformShopId) {
    editableFields.display_name = input.shopName.trim()
    editableFields.platform = requireBackendPlatform(input.platform)
  }
  return editableFields
}
