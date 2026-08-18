import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'

import {
  shopDataSource,
  type ShopListFilters,
  type ShopListItemViewModel,
  type ShopSaveInput,
  useCreateShopMutation,
  useShopDetailQuery,
  useShopListQuery,
  useShopOwnerOptionsQuery,
  useUpdateShopMutation,
} from '@/entities/shop'
import { getErrorMessage } from '@/shared/api'

import type {
  ShopFilterViewModel,
  ShopFormMode,
  ShopFormViewModel,
} from './types'

function createEmptyFilters(): ShopFilterViewModel {
  return {
    platform: null,
    enabledStatus: null,
    sessionStatus: null,
    ownerUserId: null,
    keyword: '',
  }
}

export function useShopManagement() {
  const message = useMessage()
  const filterDraft = ref<ShopFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<ShopListFilters>(createEmptyFilters())
  const page = ref(1)
  const pageSize = ref(10)
  const detailShopId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<ShopFormMode>('create')
  const formInitialValue = ref<ShopFormViewModel | null>(null)
  const editingShopId = ref<string | null>(null)

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: appliedFilters.value,
  }))
  const listQuery = useShopListQuery(listParams)
  const detailQuery = useShopDetailQuery(detailShopId)
  const ownerOptionsQuery = useShopOwnerOptionsQuery()
  const createMutation = useCreateShopMutation()
  const updateMutation = useUpdateShopMutation()

  const rows = computed(() => listQuery.data.value?.items ?? [])
  const total = computed(() => listQuery.data.value?.total ?? 0)
  const statistics = computed(() => ({
    total: total.value,
    enabled: rows.value.filter((shop) => shop.enabled).length,
    disabled: rows.value.filter((shop) => !shop.enabled).length,
  }))
  const listError = computed(() =>
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )
  const detailError = computed(() =>
    detailQuery.error.value ? getErrorMessage(detailQuery.error.value) : null,
  )
  const formSubmitting = computed(
    () => createMutation.isPending.value || updateMutation.isPending.value,
  )

  function query(): void {
    appliedFilters.value = { ...filterDraft.value }
    page.value = 1
  }

  function resetFilters(): void {
    filterDraft.value = createEmptyFilters()
    appliedFilters.value = createEmptyFilters()
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  function openDetail(shop: ShopListItemViewModel): void {
    detailShopId.value = shop.shopId
    detailVisible.value = true
  }

  function openCreate(): void {
    formMode.value = 'create'
    editingShopId.value = null
    formInitialValue.value = null
    formVisible.value = true
  }

  function openEdit(shop: ShopListItemViewModel): void {
    formMode.value = 'edit'
    editingShopId.value = shop.shopId
    formInitialValue.value = {
      shopName: shop.shopName,
      platform: shop.platform,
      enabled: shop.enabled,
      ownerUserId: shop.ownerUserId,
      note: shop.note,
    }
    formVisible.value = true
  }

  async function saveShop(form: ShopFormViewModel): Promise<void> {
    if (!form.platform) return
    const input: ShopSaveInput = { ...form, platform: form.platform }
    try {
      if (formMode.value === 'edit' && editingShopId.value) {
        await updateMutation.mutateAsync({ shopId: editingShopId.value, input })
        message.success('店铺已更新')
      } else {
        await createMutation.mutateAsync(input)
        message.success('店铺已创建')
      }
      formVisible.value = false
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  return {
    filterDraft,
    page,
    pageSize,
    detailVisible,
    formVisible,
    formMode,
    formInitialValue,
    rows,
    total,
    statistics,
    filtersAvailable: shopDataSource.supportsFilters,
    platformOptions: shopDataSource.platformOptions,
    ownerOptions: computed(() => ownerOptionsQuery.data.value ?? []),
    ownerOptionsLoading: ownerOptionsQuery.isPending,
    dataSourceDescription:
      shopDataSource.mode === 'real'
        ? '数据来自 FastAPI；会话、自动化与经营数据尚未接入。'
        : '当前数据来自 Frontend Fixture。',
    listLoading: listQuery.isPending,
    listError,
    detailShop: computed(() => detailQuery.data.value ?? null),
    detailLoading: detailQuery.isPending,
    detailError,
    formSubmitting,
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    retryDetail: detailQuery.refetch,
    openDetail,
    openCreate,
    openEdit,
    saveShop,
  }
}
