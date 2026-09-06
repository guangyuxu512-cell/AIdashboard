import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { ShopDeviceBindingInput, ShopSaveInput } from '../model/types'
import {
  shopDataSource,
  type ShopListParams,
  type ShopReferenceOptions,
} from './shop-data-source'

export const shopQueryKeys = {
  all: ['shops'] as const,
  list: (params: ShopListParams) => ['shops', 'list', params] as const,
  detail: (shopId: string | null) => ['shops', 'detail', shopId] as const,
  owners: ['shops', 'owners'] as const,
  selectionOptions: (deviceId?: string) =>
    ['shops', 'selection-options', deviceId ?? 'all'] as const,
}

export function useShopListQuery(params: MaybeRefOrGetter<ShopListParams>) {
  return useQuery({
    queryKey: computed(() => shopQueryKeys.list(toValue(params))),
    queryFn: () => shopDataSource.list(toValue(params)),
  })
}

export function useShopDetailQuery(
  shopId: MaybeRefOrGetter<string | null>,
  referenceOptions: MaybeRefOrGetter<ShopReferenceOptions>,
) {
  return useQuery({
    queryKey: computed(() => [
      ...shopQueryKeys.detail(toValue(shopId)),
      toValue(referenceOptions),
    ]),
    queryFn: () =>
      shopDataSource.get(toValue(shopId)!, toValue(referenceOptions)),
    enabled: computed(() => Boolean(toValue(shopId))),
  })
}

export function useShopOwnerOptionsQuery(enabled: MaybeRefOrGetter<boolean>) {
  return useQuery({
    queryKey: shopQueryKeys.owners,
    queryFn: () => shopDataSource.listOwnerOptions(),
    enabled: computed(() => toValue(enabled)),
  })
}

export function useShopSelectionOptionsQuery() {
  return useQuery({
    queryKey: shopQueryKeys.selectionOptions(),
    queryFn: () => shopDataSource.listSelectionOptions(),
  })
}

export function useDeviceShopSelectionOptionsQuery(
  deviceId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() =>
      shopQueryKeys.selectionOptions(toValue(deviceId) ?? undefined),
    ),
    queryFn: () => shopDataSource.listSelectionOptions(toValue(deviceId)!),
    enabled: computed(() => Boolean(toValue(deviceId))),
  })
}

export function useCreateShopMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ShopSaveInput) => shopDataSource.create(input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
  })
}

export function useUpdateShopMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ shopId, input }: { shopId: string; input: ShopSaveInput }) =>
      shopDataSource.update(shopId, input),
    onSuccess: (_, variables) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: shopQueryKeys.detail(variables.shopId),
        }),
      ]),
  })
}

export function useSetShopEnabledMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ shopId, enabled }: { shopId: string; enabled: boolean }) =>
      shopDataSource.setEnabled(shopId, enabled),
    onSuccess: (_, variables) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: shopQueryKeys.detail(variables.shopId),
        }),
      ]),
  })
}

export function useRemoveShopMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (shopId: string) => shopDataSource.remove(shopId),
    onSuccess: (_, shopId) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
        queryClient.removeQueries({
          queryKey: shopQueryKeys.detail(shopId),
        }),
      ]),
  })
}

export function useCreateShopDeviceBindingMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      shopId,
      input,
    }: {
      shopId: string
      input: ShopDeviceBindingInput
    }) => shopDataSource.createBinding(shopId, input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
  })
}

export function useUpdateShopDeviceBindingMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      shopId,
      input,
    }: {
      shopId: string
      input: ShopDeviceBindingInput
    }) => shopDataSource.updateBinding(shopId, input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: shopQueryKeys.all }),
  })
}
