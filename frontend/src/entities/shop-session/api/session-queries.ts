import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { shopSessionDataSource } from './session-data-source'

export const shopSessionQueryKeys = {
  shop: (shopId: string | null) => ['shop-sessions', 'shop', shopId] as const,
}

export function useValidateShopSessionMutation(shopId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => shopSessionDataSource.validate(toValue(shopId)),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: shopSessionQueryKeys.shop(toValue(shopId)),
      }),
  })
}

export function useAcquireShopSessionRefreshLeaseMutation(
  shopId: MaybeRefOrGetter<string>,
) {
  return useMutation({
    mutationFn: () =>
      shopSessionDataSource.acquireRefreshLease(toValue(shopId)),
  })
}

export function useReleaseShopSessionRefreshLeaseMutation() {
  return useMutation({
    mutationFn: ({ shopId, leaseId }: { shopId: string; leaseId: string }) =>
      shopSessionDataSource.releaseRefreshLease(shopId, leaseId),
  })
}

export function useShopSessionQuery(shopId: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => shopSessionQueryKeys.shop(toValue(shopId))),
    queryFn: () => shopSessionDataSource.getForShop(toValue(shopId)!),
    enabled: computed(() => Boolean(toValue(shopId))),
  })
}
