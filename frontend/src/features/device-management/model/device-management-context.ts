import { useQuery } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import {
  getYingdaoInventory,
  type YingdaoInventoryViewModel,
} from '@/entities/device'
import { SHOP_LIST_FIXTURE, shopApi } from '@/entities/shop'
import { apiMode } from '@/shared/api'

export interface DeviceManagementContext {
  inventories: Record<string, YingdaoInventoryViewModel | null>
  bindingCounts: Record<string, number | null>
}

type InventoryLoader = (
  deviceId: string,
) => Promise<YingdaoInventoryViewModel | null>

export async function loadDeviceInventories(
  deviceIds: string[],
  loadInventory: InventoryLoader = getYingdaoInventory,
): Promise<Record<string, YingdaoInventoryViewModel | null>> {
  const results = await Promise.allSettled(
    deviceIds.map((deviceId) => loadInventory(deviceId)),
  )
  return Object.fromEntries(
    deviceIds.map((deviceId, index) => [
      deviceId,
      results[index]?.status === 'fulfilled'
        ? results[index].value
        : null,
    ]),
  )
}

export async function loadDeviceBindingCounts(
  deviceIds: string[],
  loader: (ids: string[]) => Promise<Record<string, number>> =
    loadBindingCounts,
): Promise<Record<string, number | null>> {
  try {
    return await loader(deviceIds)
  } catch {
    return Object.fromEntries(deviceIds.map((deviceId) => [deviceId, null]))
  }
}

async function loadBindingCounts(
  deviceIds: string[],
): Promise<Record<string, number>> {
  const counts = Object.fromEntries(deviceIds.map((id) => [id, 0]))
  if (apiMode === 'mock') {
    for (const shop of SHOP_LIST_FIXTURE) {
      if (shop.executionDeviceId && shop.executionDeviceId in counts) {
        counts[shop.executionDeviceId]! += 1
      }
    }
    return counts
  }

  const firstPage = await shopApi.list({ page: 1, pageSize: 100 })
  const shops = [...firstPage.items]
  const pageCount = Math.ceil(firstPage.total / firstPage.page_size)
  if (pageCount > 1) {
    const remainingPages = await Promise.all(
      Array.from({ length: pageCount - 1 }, (_, index) =>
        shopApi.list({ page: index + 2, pageSize: 100 }),
      ),
    )
    shops.push(...remainingPages.flatMap((page) => page.items))
  }

  const bindingGroups = await Promise.all(
    shops.map((shop) => shopApi.listBindings(shop.shop_id)),
  )
  for (const binding of bindingGroups.flat()) {
    if (binding.enabled && binding.device_id in counts) {
      counts[binding.device_id]! += 1
    }
  }
  return counts
}

export function useDeviceManagementContextQuery(
  deviceIds: MaybeRefOrGetter<string[]>,
) {
  return useQuery({
    queryKey: computed(() => [
      'devices',
      'management-context',
      ...toValue(deviceIds),
    ]),
    queryFn: async (): Promise<DeviceManagementContext> => {
      const ids = toValue(deviceIds)
      const [inventories, bindingCounts] = await Promise.all([
        loadDeviceInventories(ids),
        loadDeviceBindingCounts(ids),
      ])
      return {
        inventories,
        bindingCounts,
      }
    },
    enabled: computed(() => toValue(deviceIds).length > 0),
    staleTime: 30_000,
  })
}
