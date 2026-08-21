import { httpClient } from '@/shared/api'

import type {
  ShopSessionHealthReadDto,
  ShopSessionMetadataReadDto,
  ShopSessionRefreshLeaseReadDto,
} from './contracts'

export const shopSessionApi = {
  async getForShop(shopId: string): Promise<ShopSessionMetadataReadDto> {
    const response = await httpClient.get<ShopSessionMetadataReadDto>(
      `/api/v1/shops/${shopId}/session`,
    )
    return response.data
  },
  async validate(shopId: string): Promise<ShopSessionHealthReadDto> {
    const response = await httpClient.post<ShopSessionHealthReadDto>(
      `/api/v1/shops/${shopId}/session/health-check`,
    )
    return response.data
  },
  async acquireRefreshLease(
    shopId: string,
  ): Promise<ShopSessionRefreshLeaseReadDto> {
    const response = await httpClient.post<ShopSessionRefreshLeaseReadDto>(
      `/api/v1/shops/${shopId}/session/refresh-lease`,
    )
    return response.data
  },
  async releaseRefreshLease(shopId: string, leaseId: string): Promise<void> {
    await httpClient.delete(
      `/api/v1/shops/${shopId}/session/refresh-lease/${leaseId}`,
    )
  },
}
