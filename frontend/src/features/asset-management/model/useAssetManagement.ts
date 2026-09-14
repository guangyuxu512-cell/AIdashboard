import { computed, ref } from 'vue'

import {
  useAssetListQuery,
  useDeleteAssetMutation,
  useUploadAssetMutation,
  type AssetListItemViewModel,
} from '@/entities/asset'
import { getErrorMessage } from '@/shared/api'

export function useAssetManagement() {
  const page = ref(1)
  const pageSize = ref(20)
  const searchDraft = ref('')
  const search = ref('')
  const listQuery = useAssetListQuery(
    computed(() => ({
      page: page.value,
      pageSize: pageSize.value,
      search: search.value,
    })),
  )
  const uploadMutation = useUploadAssetMutation()
  const deleteMutation = useDeleteAssetMutation()
  const deletingAsset = ref<AssetListItemViewModel | null>(null)

  const rows = computed(() => listQuery.data.value?.items ?? [])
  const hasData = computed(() => listQuery.data.value !== undefined)
  const listLoading = computed(() => listQuery.isPending.value && !hasData.value)
  const listError = computed(() =>
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )

  function query(): void {
    page.value = 1
    search.value = searchDraft.value.trim()
  }

  function reset(): void {
    searchDraft.value = ''
    search.value = ''
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  return {
    page,
    pageSize,
    searchDraft,
    rows,
    total: computed(() => listQuery.data.value?.total ?? 0),
    listLoading,
    listError,
    refreshing: computed(() => listQuery.isFetching.value && hasData.value),
    uploadMutation,
    deleteMutation,
    deletingAsset,
    query,
    reset,
    setPageSize,
    retry: listQuery.refetch,
  }
}
