import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { assetDataSource, type AssetListParams } from './asset-data-source'

export const assetQueryKeys = {
  all: ['assets'] as const,
  list: (params: AssetListParams) => ['assets', 'list', params] as const,
}

export function useAssetListQuery(params: MaybeRefOrGetter<AssetListParams>) {
  return useQuery({
    queryKey: computed(() => assetQueryKeys.list(toValue(params))),
    queryFn: () => assetDataSource.list(toValue(params)),
    placeholderData: keepPreviousData,
  })
}

export function useUploadAssetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => assetDataSource.upload(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetQueryKeys.all }),
  })
}

export function useDeleteAssetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (assetId: string) => assetDataSource.remove(assetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetQueryKeys.all }),
  })
}
