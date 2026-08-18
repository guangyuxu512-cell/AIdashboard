import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { ShopPlatform } from '@/entities/shop'

import type {
  CredentialCreateInput,
  CredentialUpdateInput,
} from '../model/types'
import { credentialDataSource } from './credential-data-source'

export const credentialQueryKeys = {
  all: ['credentials'] as const,
  shop: (shopId: string | null) => ['credentials', 'shop', shopId] as const,
}

export function useShopCredentialQuery(
  shopId: MaybeRefOrGetter<string | null>,
  platform: MaybeRefOrGetter<ShopPlatform | null>,
) {
  return useQuery({
    queryKey: computed(() => credentialQueryKeys.shop(toValue(shopId))),
    queryFn: () =>
      credentialDataSource.getForShop(toValue(shopId)!, toValue(platform)!),
    enabled: computed(() => Boolean(toValue(shopId) && toValue(platform))),
  })
}

export function useCreateCredentialMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: 0,
    mutationFn: (input: CredentialCreateInput) =>
      credentialDataSource.create(input),
    onSuccess: (_, input) =>
      queryClient.invalidateQueries({
        queryKey: credentialQueryKeys.shop(input.shopId),
      }),
  })
}

export function useUpdateCredentialMutation(
  shopId: MaybeRefOrGetter<string | null>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: 0,
    mutationFn: (input: CredentialUpdateInput) =>
      credentialDataSource.update(input),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: credentialQueryKeys.shop(toValue(shopId)),
      }),
  })
}
