import { useMutation, useQuery } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import type { SelectOption } from 'naive-ui'

import { apiMode } from '@/shared/api'

import { createOperatingDashboardMockSource } from './mock-source'
import type {
  OperatingDashboardFilters,
  OperatingDashboardRefreshResult,
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

function createUnavailableError(): Error {
  return new Error('经营数据查询接口暂未接入，当前无法读取经营数据。')
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

/**
 * UI-only dashboard coordinator. A Real data source is intentionally absent:
 * the Backend does not yet expose an operating-data read/update contract.
 */
export function useOperatingDashboard() {
  const filters = ref<OperatingDashboardFilters>(cloneFilters(DEFAULT_FILTERS))
  const page = ref(1)
  const pageSize = ref(10)
  const refreshFeedback = ref<OperatingDashboardRefreshFeedback | null>(null)
  const mockSource = apiMode === 'mock' ? createOperatingDashboardMockSource() : null

  const query = useQuery({
    queryKey: computed(() => [
      'operating-dashboard',
      apiMode,
      filters.value.datePreset,
      filters.value.customDateRange,
      filters.value.platform,
      filters.value.shopId,
    ]),
    queryFn: () =>
      mockSource
        ? mockSource.read(filters.value)
        : Promise.reject(createUnavailableError()),
    retry: false,
  })

  const refreshMutation = useMutation({
    mutationFn: () => {
      if (!mockSource) return Promise.reject(createUnavailableError())
      return mockSource.refresh(filters.value)
    },
    onSuccess: async (result) => {
      refreshFeedback.value = getFeedback(result)
      await query.refetch()
    },
    onError: (error) => {
      refreshFeedback.value = {
        tone: 'error',
        message:
          error instanceof Error
            ? error.message
            : '更新数据时发生未知错误。',
      }
    },
  })

  const allRows = computed<OperatingDashboardTableRow[]>(
    () => query.data.value?.tableRows ?? [],
  )
  const total = computed(() => allRows.value.length)
  const pageCount = computed(() =>
    Math.max(1, Math.ceil(total.value / pageSize.value)),
  )
  const rows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return allRows.value.slice(start, start + pageSize.value)
  })
  const shopOptions = computed<SelectOption[]>(() =>
    (query.data.value?.availableShops ?? []).map((shop) => ({
      label: shop.shopName,
      value: shop.shopId,
    })),
  )
  const platformOptions = computed<SelectOption[]>(() => {
    const platforms = new Set(
      (query.data.value?.allAvailableShops ?? []).map(
        (shop) => shop.platform,
      ),
    )
    return [
      ...(platforms.has('douyin')
        ? [{ label: '抖店', value: 'douyin' }]
        : []),
      ...(platforms.has('pdd') ? [{ label: '拼多多', value: 'pdd' }] : []),
    ]
  })

  watch(pageCount, (nextPageCount) => {
    if (page.value > nextPageCount) page.value = nextPageCount
  })

  function updateFilters(next: OperatingDashboardFilters): void {
    const currentShopExists =
      next.shopId === null ||
      (query.data.value?.availableShops ?? []).some(
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
    refreshMutation.mutate()
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
    read: query.data,
    loading: query.isFetching,
    error: computed(() =>
      query.error.value instanceof Error
        ? query.error.value.message
        : query.error.value
          ? '经营数据暂不可用。'
          : null,
    ),
    refreshFeedback,
    refreshing: refreshMutation.isPending,
    isMockMode: apiMode === 'mock',
    updateFilters,
    setPageSize,
    refresh,
    retry: () => void query.refetch(),
  }
}
