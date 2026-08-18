import dayjs from 'dayjs'

import { deviceApi } from '@/entities/device'
import { userApi } from '@/entities/user'
import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import {
  SHOP_LIST_FIXTURE,
  SHOP_OWNER_FIXTURE_OPTIONS,
  SHOP_PLATFORM_FIXTURE_OPTIONS,
} from '../fixtures/shop-list.fixture'
import type {
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
  readonly supportsFilters: boolean
  readonly platformOptions: ShopSelectOption[]
  list(params: ShopListParams): Promise<PageResult<ShopListItemViewModel>>
  get(shopId: string): Promise<ShopListItemViewModel>
  create(input: ShopSaveInput): Promise<ShopListItemViewModel>
  update(shopId: string, input: ShopSaveInput): Promise<ShopListItemViewModel>
  listOwnerOptions(): Promise<ShopSelectOption[]>
}

function cloneFixtureRows(): ShopListItemViewModel[] {
  return SHOP_LIST_FIXTURE.map((shop) => ({
    ...shop,
    backupDeviceNames: [...shop.backupDeviceNames],
  }))
}

export function createMockShopDataSource(): ShopDataSource {
  const rows = cloneFixtureRows()
  let sequence = rows.length + 1

  return {
    mode: 'mock',
    supportsFilters: true,
    platformOptions: SHOP_PLATFORM_FIXTURE_OPTIONS as ShopSelectOption[],
    async list(params) {
      const filters = params.filters
      const keyword = filters.keyword.trim().toLocaleLowerCase()
      const filtered = rows.filter((shop) => {
        const matchesKeyword =
          !keyword ||
          [shop.shopName, shop.ownerName, shop.executionDeviceName ?? ''].some(
            (value) => value.toLocaleLowerCase().includes(keyword),
          )
        return (
          matchesKeyword &&
          (!filters.platform || shop.platform === filters.platform) &&
          (!filters.enabledStatus ||
            shop.enabledStatus === filters.enabledStatus) &&
          (!filters.sessionStatus ||
            shop.sessionStatus === filters.sessionStatus) &&
          (!filters.ownerUserId || shop.ownerUserId === filters.ownerUserId)
        )
      })
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered.slice(start, start + params.pageSize),
        total: filtered.length,
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
        ownerUserId: input.ownerUserId,
        ownerName: String(owner?.label ?? '未分配'),
        enabled: input.enabled,
        enabledStatus: input.enabled ? 'enabled' : 'disabled',
        sessionStatus: 'not_configured',
        executionDeviceId: null,
        executionDeviceName: null,
        backupDeviceNames: [],
        automationStatus: 'idle',
        todayGmvDisplay: '¥0.00',
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
        accountConfigurationStatus: 'not_configured',
        sessionConfigurationStatus: 'not_configured',
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
        shopName: input.shopName,
        platform: input.platform,
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
    async listOwnerOptions() {
      return SHOP_OWNER_FIXTURE_OPTIONS.map((option) => ({
        label: String(option.label),
        value: String(option.value),
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
  supportsFilters: false,
  platformOptions: [
    { label: '抖音', value: 'douyin' },
    { label: '拼多多', value: 'pdd' },
  ],
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
  async listOwnerOptions() {
    const users = await userApi.list({ page: 1, pageSize: 100 })
    return users.items.map((user) => ({
      label: user.display_name,
      value: user.user_id,
    }))
  },
}

export function createShopDataSource(mode: ApiMode): ShopDataSource {
  return mode === 'real' ? realShopDataSource : createMockShopDataSource()
}

export const shopDataSource = createShopDataSource(apiMode)
