import dayjs from 'dayjs'

import { DEVICE_LIST_FIXTURE, deviceApi } from '@/entities/device'
import { userApi } from '@/entities/user'
import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import {
  SHOP_LIST_FIXTURE,
  SHOP_OWNER_FIXTURE_OPTIONS,
} from '../fixtures/shop-list.fixture'
import type {
  ShopDeviceBindingInput,
  ShopListFilters,
  ShopListItemViewModel,
  ShopSaveInput,
  ShopSelectOption,
} from '../model/types'
import { shopApi } from './shop-api'
import {
  mapShopCreateInput,
  mapShopDto,
  mapShopUpdateInput,
} from './shop-mapper'

export interface ShopListParams {
  page: number
  pageSize: number
  filters: ShopListFilters
}

export interface ShopDataSource {
  readonly mode: ApiMode
  list(params: ShopListParams): Promise<PageResult<ShopListItemViewModel>>
  get(shopId: string): Promise<ShopListItemViewModel>
  create(input: ShopSaveInput): Promise<ShopListItemViewModel>
  update(shopId: string, input: ShopSaveInput): Promise<ShopListItemViewModel>
  setEnabled(shopId: string, enabled: boolean): Promise<ShopListItemViewModel>
  remove(shopId: string): Promise<void>
  createBinding(shopId: string, input: ShopDeviceBindingInput): Promise<void>
  updateBinding(shopId: string, input: ShopDeviceBindingInput): Promise<void>
  listOwnerOptions(): Promise<ShopSelectOption[]>
  listSelectionOptions(): Promise<ShopSelectOption[]>
}

function cloneFixtureRows(): ShopListItemViewModel[] {
  return SHOP_LIST_FIXTURE.map((shop) => ({
    ...shop,
    backupDeviceNames: [...shop.backupDeviceNames],
    deviceBindings: shop.deviceBindings?.map((binding) => ({ ...binding })) ?? [
      ...(shop.executionDeviceId
        ? [
            {
              deviceId: shop.executionDeviceId,
              deviceName: shop.executionDeviceName ?? '未知设备',
              bindingRole: 'primary' as const,
              enabled: true,
            },
          ]
        : []),
      ...shop.backupDeviceNames.flatMap((deviceName) => {
        const device = DEVICE_LIST_FIXTURE.find(
          (item) => item.deviceName === deviceName,
        )
        return device
          ? [
              {
                deviceId: device.deviceId,
                deviceName,
                bindingRole: 'backup' as const,
                enabled: true,
              },
            ]
          : []
      }),
    ],
  }))
}

function syncFixtureBindingSummary(shop: ShopListItemViewModel): void {
  const active = (shop.deviceBindings ?? []).filter(
    (binding) => binding.enabled,
  )
  const primary = active.find((binding) => binding.bindingRole === 'primary')
  shop.executionDeviceId = primary?.deviceId ?? null
  shop.executionDeviceName = primary?.deviceName ?? null
  shop.backupDeviceNames = active
    .filter((binding) => binding.bindingRole === 'backup')
    .map((binding) => binding.deviceName)
}

export function createMockShopDataSource(): ShopDataSource {
  const rows = cloneFixtureRows()
  let sequence = rows.length + 1

  return {
    mode: 'mock',
    async list(params) {
      const start = (params.page - 1) * params.pageSize
      return {
        items: rows.slice(start, start + params.pageSize),
        total: rows.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async get(shopId) {
      const shop = rows.find((item) => item.shopId === shopId)
      if (!shop) throw new Error('店铺不存在')
      return { ...shop, backupDeviceNames: [...shop.backupDeviceNames] }
    },
    async create(input) {
      const owner = SHOP_OWNER_FIXTURE_OPTIONS.find(
        (option) => option.value === input.ownerUserId,
      )
      const shop: ShopListItemViewModel = {
        shopId: `shop-fixture-${String(sequence++).padStart(3, '0')}`,
        shopName: input.shopName,
        platform: input.platform,
        platformShopId: null,
        ownerUserId: input.ownerUserId,
        ownerName: String(owner?.label ?? '未分配'),
        enabled: input.enabled,
        enabledStatus: input.enabled ? 'enabled' : 'disabled',
        loginStatus: 'not_configured',
        executionDeviceId: null,
        executionDeviceName: null,
        backupDeviceNames: [],
        deviceBindings: [],
        createdAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
        note: input.note,
        dataSource: 'mock',
      }
      rows.unshift(shop)
      return { ...shop }
    },
    async update(shopId, input) {
      const index = rows.findIndex((item) => item.shopId === shopId)
      if (index < 0) throw new Error('店铺不存在')
      const owner = SHOP_OWNER_FIXTURE_OPTIONS.find(
        (option) => option.value === input.ownerUserId,
      )
      const updated: ShopListItemViewModel = {
        ...rows[index]!,
        shopName: rows[index]!.platformShopId
          ? rows[index]!.shopName
          : input.shopName,
        platform: rows[index]!.platformShopId
          ? rows[index]!.platform
          : input.platform,
        ownerUserId: input.ownerUserId,
        ownerName: String(owner?.label ?? '未分配'),
        enabled: input.enabled,
        enabledStatus: input.enabled ? 'enabled' : 'disabled',
        note: input.note,
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      rows[index] = updated
      return { ...updated }
    },
    async setEnabled(shopId, enabled) {
      const index = rows.findIndex((item) => item.shopId === shopId)
      if (index < 0) throw new Error('店铺不存在')
      const updated: ShopListItemViewModel = {
        ...rows[index]!,
        enabled,
        enabledStatus: enabled ? 'enabled' : 'disabled',
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      rows[index] = updated
      return { ...updated }
    },
    async remove(shopId) {
      const index = rows.findIndex((item) => item.shopId === shopId)
      if (index < 0) throw new Error('店铺不存在')
      rows.splice(index, 1)
    },
    async createBinding(shopId, input) {
      const shop = rows.find((item) => item.shopId === shopId)
      if (!shop) throw new Error('店铺不存在')
      const bindings = shop.deviceBindings ?? (shop.deviceBindings = [])
      if (bindings.some((binding) => binding.deviceId === input.deviceId)) {
        throw new Error('该店铺与设备已经存在绑定关系')
      }
      if (
        input.enabled &&
        input.bindingRole === 'primary' &&
        bindings.some(
          (binding) => binding.enabled && binding.bindingRole === 'primary',
        )
      ) {
        throw new Error('一个店铺最多只能有一个启用的主设备')
      }
      const device = DEVICE_LIST_FIXTURE.find(
        (item) => item.deviceId === input.deviceId,
      )
      bindings.push({
        deviceId: input.deviceId,
        deviceName: device?.deviceName ?? '未知设备',
        bindingRole: input.bindingRole,
        enabled: input.enabled,
      })
      syncFixtureBindingSummary(shop)
    },
    async updateBinding(shopId, input) {
      const shop = rows.find((item) => item.shopId === shopId)
      if (!shop) throw new Error('店铺不存在')
      const binding = shop.deviceBindings?.find(
        (item) => item.deviceId === input.deviceId,
      )
      if (!binding) throw new Error('设备绑定关系不存在')
      if (
        input.enabled &&
        input.bindingRole === 'primary' &&
        shop.deviceBindings?.some(
          (item) =>
            item.deviceId !== input.deviceId &&
            item.enabled &&
            item.bindingRole === 'primary',
        )
      ) {
        throw new Error('一个店铺最多只能有一个启用的主设备')
      }
      binding.bindingRole = input.bindingRole
      binding.enabled = input.enabled
      syncFixtureBindingSummary(shop)
    },
    async listOwnerOptions() {
      return SHOP_OWNER_FIXTURE_OPTIONS.map((option) => ({
        label: String(option.label),
        value: String(option.value),
      }))
    },
    async listSelectionOptions() {
      return rows.map((shop) => ({
        label: shop.shopName,
        value: shop.shopId,
        disabled: !shop.enabled,
      }))
    },
  }
}

async function loadMappingReferences() {
  const [users, devices] = await Promise.all([
    userApi.list({ page: 1, pageSize: 100 }),
    deviceApi.list({ page: 1, pageSize: 100 }),
  ])
  return { users: users.items, devices: devices.items }
}

const realShopDataSource: ShopDataSource = {
  mode: 'real',
  async list(params) {
    const [page, references] = await Promise.all([
      shopApi.list(params),
      loadMappingReferences(),
    ])
    const bindings = await Promise.all(
      page.items.map((shop) => shopApi.listBindings(shop.shop_id)),
    )
    return {
      items: page.items.map((shop, index) =>
        mapShopDto(shop, { ...references, bindings: bindings[index] ?? [] }),
      ),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  async get(shopId) {
    const [shop, references, bindings] = await Promise.all([
      shopApi.get(shopId),
      loadMappingReferences(),
      shopApi.listBindings(shopId),
    ])
    return mapShopDto(shop, { ...references, bindings })
  },
  async create(input) {
    const shop = await shopApi.create(mapShopCreateInput(input))
    const references = await loadMappingReferences()
    return mapShopDto(shop, { ...references, bindings: [] })
  },
  async update(shopId, input) {
    const [shop, references, bindings] = await Promise.all([
      shopApi.update(shopId, mapShopUpdateInput(input)),
      loadMappingReferences(),
      shopApi.listBindings(shopId),
    ])
    return mapShopDto(shop, { ...references, bindings })
  },
  async setEnabled(shopId, enabled) {
    const [shop, references, bindings] = await Promise.all([
      shopApi.update(shopId, { enabled }),
      loadMappingReferences(),
      shopApi.listBindings(shopId),
    ])
    return mapShopDto(shop, { ...references, bindings })
  },
  async remove(shopId) {
    await shopApi.remove(shopId)
  },
  async createBinding(shopId, input) {
    await shopApi.createBinding(shopId, {
      device_id: input.deviceId,
      binding_role: input.bindingRole,
      enabled: input.enabled,
    })
  },
  async updateBinding(shopId, input) {
    await shopApi.updateBinding(shopId, input.deviceId, {
      binding_role: input.bindingRole,
      enabled: input.enabled,
    })
  },
  async listOwnerOptions() {
    const users = await userApi.list({ page: 1, pageSize: 100 })
    return users.items.map((user) => ({
      label: user.display_name,
      value: user.user_id,
    }))
  },
  async listSelectionOptions() {
    const page = await shopApi.list({ page: 1, pageSize: 100 })
    return page.items.map((shop) => ({
      label: shop.display_name,
      value: shop.shop_id,
      disabled: !shop.enabled,
    }))
  },
}

export function createShopDataSource(mode: ApiMode): ShopDataSource {
  return mode === 'real' ? realShopDataSource : createMockShopDataSource()
}

export const shopDataSource = createShopDataSource(apiMode)
