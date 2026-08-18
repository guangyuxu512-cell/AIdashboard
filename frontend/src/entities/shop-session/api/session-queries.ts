import { useQuery } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { shopSessionDataSource } from './session-data-source'

export const shopSessionQueryKeys = {
  shop: (shopId: string | null) => ['shop-sessions', 'shop', shopId] as const,
}

export function useShopSessionQuery(shopId: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => shopSessionQueryKeys.shop(toValue(shopId))),
    queryFn: () => shopSessionDataSource.getForShop(toValue(shopId)!),
    enabled: computed(() => Boolean(toValue(shopId))),
  })
}
