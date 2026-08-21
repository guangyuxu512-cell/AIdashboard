import { apiMode } from '@/shared/api'

import { YINGDAO_INVENTORY_FIXTURE_BY_DEVICE } from '../fixtures/yingdao-inventory.fixture'
import type { YingdaoInventoryViewModel } from '../model/types'
import { deviceApi } from './device-api'
import { mapYingdaoInventoryDto } from './device-mapper'

export async function getYingdaoInventory(
  deviceId: string,
): Promise<YingdaoInventoryViewModel | null> {
  if (apiMode === 'mock') {
    const inventory = YINGDAO_INVENTORY_FIXTURE_BY_DEVICE[deviceId]
    return inventory
      ? {
          ...inventory,
          applications: inventory.applications.map((app) => ({ ...app })),
        }
      : null
  }

  const inventories = await deviceApi.getProviderInventories(deviceId)
  const yingdao = inventories.find(
    (inventory) => inventory.provider_code === 'yingdao',
  )
  return yingdao ? mapYingdaoInventoryDto(yingdao) : null
}
