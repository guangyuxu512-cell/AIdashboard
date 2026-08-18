import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type { UserReadDto } from './contracts'

export const userApi = {
  async list(params: PageParams): Promise<PageDto<UserReadDto>> {
    const response = await httpClient.get<PageDto<UserReadDto>>(
      '/api/v1/users',
      {
        params: { page: params.page, page_size: params.pageSize },
      },
    )
    return response.data
  },
}
