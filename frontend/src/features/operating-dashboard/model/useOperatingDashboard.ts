import { keepPreviousData, useMutation, useQuery } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import type { SelectOption } from 'naive-ui'

import {
  type ShopListFilters,
  type ShopListParams,
  type ShopReferenceOptions,
  useShopDetailQuery,
  useShopListQuery,
} from '@/entities/shop'
import { getPlatformDefinition } from '@/entities/platform'
import { apiMode } from '@/shared/api'

import { buildOperatingDashboardUnavailableRead } from './dashboard'
import { createOperatingDashboardMockSource } from './mock-source'
import type {
  OperatingDashboardFilters,
  OperatingDashboardRefreshResult,
  OperatingDashboardShopOption,
  OperatingDashboardTableRow,
} from './types'

export interface OperatingDashboardRefreshFeedback {
  tone: 'success' | 'warning' | 'error'
  message: string
}

const DEFAULT_FILTERS: OperatingDashboardFilters = {
  datePreset: 'yesterday',
  customDateRange: null,
  platform: null,
  shopId: null,
}

const EMPTY_SHOP_FILTERS = {
  enabledStatus: null,
  ownerUserId: null,
  keyword: '',
} satisfies ShopListFilters

const DASHBOARD_SHOP_REFERENCES = {
  includeOwners: false,
  includeDevices: false,
} satisfies ShopReferenceOptions

function cloneFilters(
  filters: OperatingDashboardFilters,
): OperatingDashboardFilters {
  return {
    ...filters,
    customDateRange: filters.customDateRange
      ? [...filters.customDateRange] as [number, number]
      : null,
  }
}

function sameFilters(
  left: OperatingDashboardFilters,
  right: OperatingDashboardFilters,
): boolean {
  return (
    left.datePreset === right.datePreset &&
    left.platform === right.platform &&
    left.shopId === right.shopId &&
    left.customDateRange?.[0] === right.customDateRange?.[0] &&
    left.customDateRange?.[1] === right.customDateRange?.[1]
  )
}

function getFeedback(
  result: OperatingDashboardRefreshResult,
): OperatingDashboardRefreshFeedback {
  if (result.status === 'completed') {
    return {
      tone: 'success',
      message: `已完成 ${result.refreshedShopCount} 家店铺的数据更新。`,
    }
  }
  if (result.status === 'partial_failure') {
    return {
      tone: 'warning',
      message: `已更新 ${result.refreshedShopCount} 家；${result.failedShopNames.join('、')} 暂未更新，可再次尝试。`,
    }
  }
  return {
    tone: 'error',
    message:
      result.failedShopNames.length > 0
        ? `${result.failedShopNames.join('、')} 未完成更新，可再次尝试。`
        : '当前筛选范围没有可更新的店铺。',
  }
}

function toDashboardShopOption(shop: {
  shopId: string
  shopName: string
  platform: OperatingDashboardShopOption['platform']
}): OperatingDashboardShopOption {
  return {
    shopId: shop.shopId,
    shopName: shop.shopName,
    platform: shop.platform,
  }
}

/**
 * UI-only dashboard coordinator. Real mode deliberately reads only the
 * existing authorized Shop Contract for identity and scope; no operating-data
 * read or refresh endpoint is invented before its backend contract exists.
 */
export function useOperatingDashboard() {
  const filters = ref<OperatingDashboardFilters>(cloneFilters(DEFAULT_FILTERS))
  const page = ref(1)
  const pageSize = ref(10)
  const refreshFeedback = ref<OperatingDashboardRefreshFeedback | null>(null)
  const isMockMode = apiMode === 'mock'
  const mockSource = isMockMode ? createOperatingDashboardMockSource() : null

  const mockQuery = useQuery({
    queryKey: computed(() => [
      'operating-dashboard',
      apiMode,
      filters.value.datePreset,
      filters.value.customDateRange,
      filters.value.platform,
      filters.value.shopId,
    ]),
    queryFn: () => mockSource!.read(cloneFilters(filters.value)),
    enabled: isMockMode,
    placeholderData: keepPreviousData,
    retry: false,
  })

  const realListParams = computed<ShopListParams>(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: EMPTY_SHOP_FILTERS,
    platform: filters.value.platform ?? 'all',
    referenceOptions: DASHBOARD_SHOP_REFERENCES,
  }))
  const realShopListQuery = useShopListQuery(
    realListParams,
    () => !isMockMode && filters.value.shopId === null,
  )
  const realShopOptionsQuery = useShopListQuery(
    computed(() => ({
      page: 1,
      pageSize: 100,
      filters: EMPTY_SHOP_FILTERS,
      platform: 'all' as const,
      referenceOptions: DASHBOARD_SHOP_REFERENCES,
    })),
    () => !isMockMode,
  )
  const selectedRealShopId = computed(() =>
    isMockMode ? null : filters.value.shopId,
  )
  const selectedRealShopQuery = useShopDetailQuery(
    selectedRealShopId,
    DASHBOARD_SHOP_REFERENCES,
  )

  const realShopOptions = computed<OperatingDashboardShopOption[]>(() =>
    (realShopOptionsQuery.data.value?.items ?? []).map(toDashboardShopOption),
  )
  const selectedRealShop = computed(() => {
    const shop = selectedRealShopQuery.data.value
    if (!shop) return null
    if (filters.value.platform && shop.platform !== filters.value.platform) {
      return null
    }
    return toDashboardShopOption(shop)
  })
  const realTableShops = computed<OperatingDashboardShopOption[]>(() => {
    if (filters.value.shopId) {
      return selectedRealShop.value ? [selectedRealShop.value] : []
    }
    return (realShopListQuery.data.value?.items ?? []).map(
      toDashboardShopOption,
    )
  })
  const realShopCount = computed<number | null>(() => {
    if (filters.value.shopId) {
      if (selectedRealShopQuery.isSuccess.value) {
        return selectedRealShop.value ? 1 : 0
      }
      return null
    }
    return realShopListQuery.isSuccess.value
      ? realShopListQuery.data.value?.total ?? 0
      : null
  })
  const realUnavailable = computed(() =>
    filters.value.shopId
      ? Boolean(selectedRealShopQuery.error.value)
      : Boolean(realShopListQuery.error.value),
  )
  const realLoading = computed(() =>
    filters.value.shopId
      ? selectedRealShopQuery.isPending.value
      : realShopListQuery.isPending.value,
  )
  const realRead = computed(() =>
    buildOperatingDashboardUnavailableRead(
      filters.value,
      realShopOptions.value,
      realTableShops.value,
      realShopCount.value,
    ),
  )

  const refreshMutation = useMutation({
    mutationFn: (requestFilters: OperatingDashboardFilters) =>
      mockSource!.refresh(requestFilters),
    onSuccess: async (result, requestFilters) => {
      if (!sameFilters(requestFilters, filters.value)) return
      refreshFeedback.value = getFeedback(result)
      await mockQuery.refetch()
    },
    onError: (error, requestFilters) => {
      if (!sameFilters(requestFilters, filters.value)) return
      refreshFeedback.value = {
        tone: 'error',
        message:
          error instanceof Error
            ? error.message
            : '更新数据时发生未知错误。',
      }
    },
  })

  const read = computed(() =>
    mockQuery.data.value ?? (!isMockMode ? realRead.value : undefined),
  )
  const allRows = computed<OperatingDashboardTableRow[]>(
    () => read.value?.tableRows ?? [],
  )
  const total = computed(() =>
    isMockMode ? allRows.value.length : realShopCount.value ?? 0,
  )
  const pageCount = computed(() =>
    Math.max(1, Math.ceil(total.value / pageSize.value)),
  )
  const rows = computed(() => {
    if (!isMockMode) return allRows.value
    const start = (page.value - 1) * pageSize.value
    return allRows.value.slice(start, start + pageSize.value)
  })
  const shopOptions = computed<SelectOption[]>(() => {
    const shops = isMockMode
      ? read.value?.allAvailableShops ?? []
      : realShopOptions.value
    return shops
      .filter(
        (shop) =>
          filters.value.platform === null ||
          shop.platform === filters.value.platform,
      )
      .map((shop) => ({ label: shop.shopName, value: shop.shopId }))
  })
  const platformOptions = computed<SelectOption[]>(() => {
    const shops = isMockMode
      ? read.value?.allAvailableShops ?? []
      : realShopOptions.value
    const platforms = new Set(shops.map((shop) => shop.platform))
    return [...platforms].flatMap((platform) => {
      const definition = getPlatformDefinition(platform)
      return definition
        ? [{ label: definition.label, value: definition.code }]
        : []
    })
  })
  const tableEmptyDescription = computed(() => {
    if (!isMockMode && realUnavailable.value) return '经营数据暂不可用'
    if (!isMockMode && realShopCount.value === 0) return '暂无店铺'
    return '当前筛选范围暂无经营数据'
  })

  watch(pageCount, (nextPageCount) => {
    if (page.value > nextPageCount) page.value = nextPageCount
  })
  watch(
    () => [filters.value.platform, selectedRealShopQuery.data.value] as const,
    ([platform, shop]) => {
      if (
        isMockMode ||
        !filters.value.shopId ||
        !platform ||
        !shop ||
        shop.platform === platform
      ) {
        return
      }
      filters.value = { ...filters.value, shopId: null }
    },
  )

  function updateFilters(next: OperatingDashboardFilters): void {
    const knownShops = isMockMode
      ? read.value?.allAvailableShops ?? []
      : realShopOptions.value
    const optionsResolved = isMockMode || realShopOptionsQuery.isSuccess.value
    const currentShopExists =
      next.shopId === null ||
      !optionsResolved ||
      knownShops.some(
        (shop) =>
          shop.shopId === next.shopId &&
          (next.platform === null || shop.platform === next.platform),
      )
    filters.value = {
      ...cloneFilters(next),
      shopId: currentShopExists ? next.shopId : null,
    }
    refreshFeedback.value = null
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  function refresh(): void {
    if (!mockSource || refreshMutation.isPending.value) return
    refreshMutation.mutate(cloneFilters(filters.value))
  }

  return {
    apiMode,
    filters,
    page,
    pageSize,
    total,
    rows,
    allRows,
    shopOptions,
    platformOptions,
    read,
    initialLoading: computed(
      () =>
        isMockMode &&
        mockQuery.isPending.value &&
        mockQuery.data.value === undefined,
    ),
    filterLoading: computed(() =>
      isMockMode
        ? mockQuery.isFetching.value && mockQuery.data.value !== undefined
        : realLoading.value,
    ),
    tableEmptyDescription,
    refreshFeedback,
    refreshing: refreshMutation.isPending,
    isMockMode,
    updateFilters,
    setPageSize,
    refresh,
  }
}
