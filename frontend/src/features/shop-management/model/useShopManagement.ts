import dayjs from 'dayjs'
import { useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  shopDataSource,
  type ShopListFilters,
  type ShopListItemViewModel,
  type ShopPlatformFilter,
  type ShopReferenceOptions,
  type ShopSaveInput,
  useCreateShopMutation,
  useRemoveShopMutation,
  useSetShopEnabledMutation,
  useShopDetailQuery,
  useShopListQuery,
  useShopOwnerOptionsQuery,
  useUpdateShopMutation,
} from '@/entities/shop'
import { getErrorMessage } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'

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
  const auth = useAuthStore()
  const filterDraft = ref<ShopFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<ShopListFilters>(createEmptyFilters())
  const selectedPlatform = ref<ShopPlatformFilter>('all')
  const page = ref(1)
  const pageSize = ref(10)
  const selectedShopIds = ref<string[]>([])
  const detailShopId = ref<string | null>(null)
  const detailVisible = ref(false)
  const onboardingVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<ShopFormMode>('create')
  const formInitialValue = ref<ShopFormViewModel | null>(null)
  const editingShopId = ref<string | null>(null)
  const statusChangingShopId = ref<string | null>(null)
  const removeShop = ref<ShopListItemViewModel | null>(null)
  const removeVisible = ref(false)

  const canManageOwners = computed(() => auth.isAccessAdministrator)
  const canReadDevices = computed(() => auth.allowedModuleCodes.has('device'))
  const referenceOptions = computed<ShopReferenceOptions>(() => ({
    includeOwners: canManageOwners.value,
    includeDevices: canReadDevices.value,
  }))
  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: appliedFilters.value,
    platform: selectedPlatform.value,
    referenceOptions: referenceOptions.value,
  }))
  const listQuery = useShopListQuery(listParams)
  const detailQuery = useShopDetailQuery(detailShopId, referenceOptions)
  const ownerOptionsQuery = useShopOwnerOptionsQuery(canManageOwners)
  const createMutation = useCreateShopMutation()
  const updateMutation = useUpdateShopMutation()
  const setEnabledMutation = useSetShopEnabledMutation()
  const removeMutation = useRemoveShopMutation()

  const sourceRows = computed(() => listQuery.data.value?.items ?? [])
  const rows = computed(() => sourceRows.value)
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
  watch(selectedPlatform, () => {
    page.value = 1
  }, { flush: 'sync' })

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
    onboardingVisible.value = true
  }

  function openLegacyCreate(): void {
    formMode.value = 'create'
    editingShopId.value = null
    formInitialValue.value = null
    formVisible.value = true
  }

  async function handleOnboardingCompleted(shopId: string): Promise<void> {
    selectedShopIds.value = [shopId]
    await listQuery.refetch()
  }

  function openEdit(shop: ShopListItemViewModel): void {
    formMode.value = 'edit'
    editingShopId.value = shop.shopId
    formInitialValue.value = {
      shopName: shop.shopName,
      platform: shop.platform,
      platformShopId: shop.platformShopId ?? null,
      enabled: shop.enabled,
      ownerUserId: shop.ownerUserId,
      note: shop.note,
      operatingStartDate: shop.operatingStartDate
        ? dayjs(shop.operatingStartDate).valueOf()
        : null,
    }
    formVisible.value = true
  }

  function editFromDetail(shop: ShopListItemViewModel): void {
    detailVisible.value = false
    openEdit(shop)
  }

  async function saveShop(form: ShopFormViewModel): Promise<void> {
    if (!form.platform) return
    const input: ShopSaveInput = {
      ...form,
      platform: form.platform,
      operatingStartDate:
        form.operatingStartDate === null
          ? null
          : dayjs(form.operatingStartDate).format('YYYY-MM-DD'),
    }
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

  async function toggleEnabled(shop: ShopListItemViewModel): Promise<void> {
    statusChangingShopId.value = shop.shopId
    try {
      await setEnabledMutation.mutateAsync({
        shopId: shop.shopId,
        enabled: !shop.enabled,
      })
      message.success(shop.enabled ? '店铺已停用' : '店铺已启用')
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      statusChangingShopId.value = null
    }
  }

  function requestRemove(shop: ShopListItemViewModel): void {
    removeShop.value = shop
    removeVisible.value = true
  }

  async function confirmRemove(): Promise<void> {
    const shop = removeShop.value
    if (!shop) return
    try {
      await removeMutation.mutateAsync(shop.shopId)
      selectedShopIds.value = selectedShopIds.value.filter(
        (shopId) => shopId !== shop.shopId,
      )
      if (detailShopId.value === shop.shopId) {
        detailVisible.value = false
        detailShopId.value = null
      }
      removeVisible.value = false
      removeShop.value = null
      if (rows.value.length === 1 && page.value > 1) page.value -= 1
      message.success('店铺已移除')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function refreshList(): Promise<void> {
    await listQuery.refetch()
  }

  return {
    filterDraft,
    selectedPlatform,
    page,
    pageSize,
    selectedShopIds,
    selectedShopCount,
    detailVisible,
    onboardingVisible,
    formVisible,
    formMode,
    formInitialValue,
    statusChangingShopId,
    removeShop,
    removeVisible,
    rows,
    total,
    ownerOptions: computed(() => ownerOptionsQuery.data.value ?? []),
    ownerOptionsLoading: ownerOptionsQuery.isPending,
    canManageOwners,
    canReadDevices,
    dataSourceDescription:
      shopDataSource.mode === 'real'
        ? '数据来自 FastAPI；筛选在授权范围内分页前执行。'
        : '当前数据来自 Frontend Fixture；筛选在分页前执行。',
    listLoading: listQuery.isPending,
    listError,
    detailShop: computed(() => detailQuery.data.value ?? null),
    detailLoading: detailQuery.isPending,
    detailError,
    formSubmitting,
    removeSubmitting: computed(() => removeMutation.isPending.value),
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    retryDetail: detailQuery.refetch,
    openDetail,
    openCreate,
    openLegacyCreate,
    handleOnboardingCompleted,
    openEdit,
    editFromDetail,
    saveShop,
    toggleEnabled,
    requestRemove,
    confirmRemove,
    refreshList,
  }
}
