import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import {
  deviceApi,
  getYingdaoInventory,
  type DeviceLocalShopInventoryDto,
  type YingdaoInventoryViewModel,
} from '@/entities/device'
import { apiMode } from '@/shared/api'

export interface DeviceManagementContext {
  inventories: Record<string, YingdaoInventoryViewModel | null>
  localShops: Record<string, DeviceLocalShopInventoryDto | null>
}

type InventoryLoader = (
  deviceId: string,
) => Promise<YingdaoInventoryViewModel | null>

export async function loadDeviceInventories(
  deviceIds: string[],
  loadInventory: InventoryLoader = getYingdaoInventory,
  previous: Record<string, YingdaoInventoryViewModel | null> = {},
): Promise<Record<string, YingdaoInventoryViewModel | null>> {
  const results = await Promise.allSettled(
    deviceIds.map((deviceId) => loadInventory(deviceId)),
  )
  return Object.fromEntries(
    deviceIds.map((deviceId, index) => [
      deviceId,
      results[index]?.status === 'fulfilled'
        ? results[index].value
        : (previous[deviceId] ?? null),
    ]),
  )
}

export async function loadDeviceLocalShops(
  deviceIds: string[],
  loader: (deviceId: string) => Promise<DeviceLocalShopInventoryDto | null> =
    (deviceId) => apiMode === 'mock'
      ? Promise.resolve(null)
      : deviceApi.getLocalShops(deviceId),
  previous: Record<string, DeviceLocalShopInventoryDto | null> = {},
): Promise<Record<string, DeviceLocalShopInventoryDto | null>> {
  const results = await Promise.allSettled(
    deviceIds.map((deviceId) => loader(deviceId)),
  )
  return Object.fromEntries(deviceIds.map((deviceId, index) => [
    deviceId,
    results[index]?.status === 'fulfilled'
      ? results[index].value
      : (previous[deviceId] ?? null),
  ]))
}

export function useDeviceManagementContextQuery(
  deviceIds: MaybeRefOrGetter<string[]>,
) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: computed(() => [
      'devices',
      'management-context',
      ...toValue(deviceIds),
    ]),
    queryFn: async (): Promise<DeviceManagementContext> => {
      const ids = toValue(deviceIds)
      const previous = queryClient.getQueryData<DeviceManagementContext>([
        'devices',
        'management-context',
        ...ids,
      ])
      const [inventories, localShops] = await Promise.all([
        loadDeviceInventories(ids, getYingdaoInventory, previous?.inventories),
        loadDeviceLocalShops(ids, undefined, previous?.localShops),
      ])
      return {
        inventories,
        localShops,
      }
    },
    enabled: computed(() => toValue(deviceIds).length > 0),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  })
}
