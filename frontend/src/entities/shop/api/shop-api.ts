import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type {
  ShopCreateDto,
  ShopDeviceBindingCreateDto,
  ShopDeviceBindingReadDto,
  ShopDeviceBindingUpdateDto,
  ShopReadDto,
  ShopUpdateDto,
} from './contracts'

export const shopApi = {
  async list(params: PageParams): Promise<PageDto<ShopReadDto>> {
    const response = await httpClient.get<PageDto<ShopReadDto>>(
      '/api/v1/shops',
      {
        params: { page: params.page, page_size: params.pageSize },
      },
    )
    return response.data
  },

  async get(shopId: string): Promise<ShopReadDto> {
    const response = await httpClient.get<ShopReadDto>(
      `/api/v1/shops/${shopId}`,
    )
    return response.data
  },

  async create(data: ShopCreateDto): Promise<ShopReadDto> {
    const response = await httpClient.post<ShopReadDto>('/api/v1/shops', data)
    return response.data
  },

  async update(shopId: string, data: ShopUpdateDto): Promise<ShopReadDto> {
    const response = await httpClient.patch<ShopReadDto>(
      `/api/v1/shops/${shopId}`,
      data,
    )
    return response.data
  },

  async listBindings(shopId: string): Promise<ShopDeviceBindingReadDto[]> {
    const response = await httpClient.get<ShopDeviceBindingReadDto[]>(
      `/api/v1/shops/${shopId}/device-bindings`,
    )
    return response.data
  },

  async createBinding(
    shopId: string,
    data: ShopDeviceBindingCreateDto,
  ): Promise<ShopDeviceBindingReadDto> {
    const response = await httpClient.post<ShopDeviceBindingReadDto>(
      `/api/v1/shops/${shopId}/device-bindings`,
      data,
    )
    return response.data
  },

  async updateBinding(
    shopId: string,
    deviceId: string,
    data: ShopDeviceBindingUpdateDto,
  ): Promise<ShopDeviceBindingReadDto> {
    const response = await httpClient.patch<ShopDeviceBindingReadDto>(
      `/api/v1/shops/${shopId}/device-bindings/${deviceId}`,
      data,
    )
    return response.data
  },
}
