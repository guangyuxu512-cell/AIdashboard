import { httpClient } from '@/shared/api'

import type {
  CredentialCreateDto,
  CredentialStatusReadDto,
  CredentialUpdateDto,
} from './contracts'

export const credentialApi = {
  async getForShop(shopId: string): Promise<CredentialStatusReadDto> {
    const response = await httpClient.get<CredentialStatusReadDto>(
      `/api/v1/shops/${shopId}/credential`,
    )
    return response.data
  },

  async create(data: CredentialCreateDto): Promise<CredentialStatusReadDto> {
    const response = await httpClient.post<CredentialStatusReadDto>(
      '/api/v1/credentials',
      data,
    )
    return response.data
  },

  async update(
    credentialId: string,
    data: CredentialUpdateDto,
  ): Promise<CredentialStatusReadDto> {
    const response = await httpClient.patch<CredentialStatusReadDto>(
      `/api/v1/credentials/${credentialId}`,
      data,
    )
    return response.data
  },

  async disable(credentialId: string): Promise<CredentialStatusReadDto> {
    const response = await httpClient.post<CredentialStatusReadDto>(
      `/api/v1/credentials/${credentialId}/disable`,
    )
    return response.data
  },
}
