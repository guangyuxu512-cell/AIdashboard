import { httpClient } from '@/shared/api'

import type { ShopSessionMetadataReadDto } from './contracts'

export const shopSessionApi = {
  async getForShop(shopId: string): Promise<ShopSessionMetadataReadDto> {
    const response = await httpClient.get<ShopSessionMetadataReadDto>(
      `/api/v1/shops/${shopId}/session`,
    )
    return response.data
  },
}
