import { useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  shopDataSource,
  type ShopListFilters,
  type ShopListItemViewModel,
  type ShopPlatformFilter,
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
    enabledStatus: null,
    ownerUserId: null,
    keyword: '',
  }
}

export function useShopManagement() {
  const message = useMessage()
  const filterDraft = ref<ShopFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<ShopListFilters>(createEmptyFilters())
  const selectedPlatform = ref<ShopPlatformFilter>('all')
  const page = ref(1)
  const pageSize = ref(10)
  const selectedShopIds = ref<string[]>([])
  const detailShopId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<ShopFormMode>('create')
  const formInitialValue = ref<ShopFormViewModel | null>(null)
  const editingShopId = ref<string | null>(null)

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    // Backend V1 only accepts pagination. All visible filters are applied to
    // the already-loaded page and must never become invented query params.
    filters: createEmptyFilters(),
  }))
  const listQuery = useShopListQuery(listParams)
  const detailQuery = useShopDetailQuery(detailShopId)
  const ownerOptionsQuery = useShopOwnerOptionsQuery()
  const createMutation = useCreateShopMutation()
  const updateMutation = useUpdateShopMutation()

  const sourceRows = computed(() => listQuery.data.value?.items ?? [])
  const rows = computed(() => {
    const filters = appliedFilters.value
    const keyword = filters.keyword.trim().toLocaleLowerCase()
    return sourceRows.value.filter(
      (shop) =>
        (selectedPlatform.value === 'all' ||
          shop.platform === selectedPlatform.value) &&
        (!filters.enabledStatus ||
          shop.enabledStatus === filters.enabledStatus) &&
        (!filters.ownerUserId || shop.ownerUserId === filters.ownerUserId) &&
        (!keyword || shop.shopName.toLocaleLowerCase().includes(keyword)),
    )
  })
  const selectedShopCount = computed(() => selectedShopIds.value.length)
  const total = computed(() => listQuery.data.value?.total ?? 0)
  const listError = computed(() =>
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )
  const detailError = computed(() =>
    detailQuery.error.value ? getErrorMessage(detailQuery.error.value) : null,
  )
  const formSubmitting = computed(
    () => createMutation.isPending.value || updateMutation.isPending.value,
  )

  watch(rows, (currentRows) => {
    const currentIds = new Set(currentRows.map((shop) => shop.shopId))
    selectedShopIds.value = selectedShopIds.value.filter((shopId) =>
      currentIds.has(shopId),
    )
  })

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

  function editFromDetail(shop: ShopListItemViewModel): void {
    detailVisible.value = false
    openEdit(shop)
  }

  async function saveShop(form: ShopFormViewModel): Promise<void> {
    if (!form.platform) return
    const input: ShopSaveInput = { ...form, platform: form.platform }
    try {
      if (formMode.value === 'edit' && editingShopId.value) {
        await updateMutation.mutateAsync({ shopId: editingShopId.value, input })
        message.success('店铺已更新')
      } else {
        const createdShop = await createMutation.mutateAsync(input)
        selectedShopIds.value = [createdShop.shopId]
        message.success('店铺已创建')
      }
      formVisible.value = false
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  return {
    filterDraft,
    selectedPlatform,
    page,
    pageSize,
    selectedShopIds,
    selectedShopCount,
    detailVisible,
    formVisible,
    formMode,
    formInitialValue,
    rows,
    total,
    ownerOptions: computed(() => ownerOptionsQuery.data.value ?? []),
    ownerOptionsLoading: ownerOptionsQuery.isPending,
    dataSourceDescription:
      shopDataSource.mode === 'real'
        ? '数据来自 FastAPI；平台与筛选条件仅筛选当前页。'
        : '当前数据来自 Frontend Fixture；平台与筛选条件仅筛选当前页。',
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
    editFromDetail,
    saveShop,
  }
}
