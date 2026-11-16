import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import type { SelectOption } from 'naive-ui'

import { getPlatformDefinition } from '@/entities/platform'
import { apiMode, getErrorMessage } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'
import { operatingDashboardApi } from '../api/operating-dashboard-api'
import { resolveOperatingDashboardDateRange, sortOperatingDashboardRows } from './dashboard'
import { createOperatingDashboardMockSource } from './mock-source'
import type { OperatingDashboardFilters, OperatingDashboardSort, OperatingDashboardTableRow } from './types'

const DEFAULT_FILTERS: OperatingDashboardFilters = {
  datePreset: 'yesterday', customDateRange: null, platform: null, shopId: null,
}

function cloneFilters(filters: OperatingDashboardFilters): OperatingDashboardFilters {
  return {
    ...filters,
    customDateRange: filters.customDateRange
      ? ([...filters.customDateRange] as [number, number])
      : null,
  }
}

/** Historical data only; collection is paused until a Worker implementation exists. */
export function useOperatingDashboard() {
  const auth = useAuthStore()
  const filters = ref<OperatingDashboardFilters>(cloneFilters(DEFAULT_FILTERS))
  const sort = ref<OperatingDashboardSort | null>(null)
  const page = ref(1)
  const pageSize = ref(10)
  const isMockMode = apiMode === 'mock'
  const mockSource = isMockMode ? createOperatingDashboardMockSource() : null
  const dateRange = computed(() => resolveOperatingDashboardDateRange(filters.value))

  const mockQuery = useQuery({
    queryKey: computed(() => ['operating-dashboard', 'mock', filters.value.datePreset,
      filters.value.customDateRange, filters.value.platform, filters.value.shopId]),
    queryFn: () => mockSource!.read(cloneFilters(filters.value)),
    enabled: isMockMode,
    placeholderData: keepPreviousData,
    retry: false,
  })
  const realQuery = useQuery({
    queryKey: computed(() => ['operating-dashboard', 'real', auth.currentUser?.userId ?? null,
      auth.activeTeamId, auth.isSuperAccount, dateRange.value.startDate, dateRange.value.endDate,
      filters.value.platform, filters.value.shopId, sort.value?.field ?? null,
      sort.value?.direction ?? null, page.value, pageSize.value]),
    queryFn: () => operatingDashboardApi.read({
      range: dateRange.value, filters: cloneFilters(filters.value), sort: sort.value,
      page: page.value, pageSize: pageSize.value,
    }),
    enabled: !isMockMode,
    retry: false,
  })

  const read = computed(() => isMockMode ? mockQuery.data.value : realQuery.data.value)
  const allRows = computed<OperatingDashboardTableRow[]>(() => read.value?.tableRows ?? [])
  const sortedRows = computed(() => isMockMode ? sortOperatingDashboardRows(allRows.value, sort.value) : allRows.value)
  const total = computed(() => isMockMode ? sortedRows.value.length : (read.value?.tablePage.total ?? 0))
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const rows = computed(() => {
    if (!isMockMode) return sortedRows.value
    const start = (page.value - 1) * pageSize.value
    return sortedRows.value.slice(start, start + pageSize.value)
  })
  const shopOptions = computed<SelectOption[]>(() => (read.value?.allAvailableShops ?? [])
    .filter((shop) => filters.value.platform === null || shop.platform === filters.value.platform)
    .map((shop) => ({ label: shop.shopName, value: shop.shopId })))
  const platformOptions = computed<SelectOption[]>(() => {
    const platforms = new Set((read.value?.allAvailableShops ?? []).map((shop) => shop.platform))
    return [...platforms].flatMap((platform) => {
      const definition = getPlatformDefinition(platform)
      return definition ? [{ label: definition.label, value: definition.code }] : []
    })
  })
  const tableEmptyDescription = computed(() =>
    !isMockMode && realQuery.isError.value ? '经营数据读取失败，请重试' : '当前筛选范围暂无经营数据')
  const readErrorMessage = computed(() =>
    !isMockMode && realQuery.error.value ? getErrorMessage(realQuery.error.value) : '经营数据暂不可用')

  watch(pageCount, (next) => { if (page.value > next) page.value = next })
  function updateFilters(next: OperatingDashboardFilters): void {
    const knownShops = read.value?.allAvailableShops ?? []
    const currentShopExists = next.shopId === null || knownShops.length === 0 ||
      knownShops.some((shop) => shop.shopId === next.shopId &&
        (next.platform === null || shop.platform === next.platform))
    filters.value = { ...cloneFilters(next), shopId: currentShopExists ? next.shopId : null }
    page.value = 1
  }
  function setPageSize(value: number): void { pageSize.value = value; page.value = 1 }
  function setSort(value: OperatingDashboardSort | null): void { sort.value = value; page.value = 1 }
  function retryRead(): void { void (isMockMode ? mockQuery.refetch() : realQuery.refetch()) }

  return {
    apiMode, filters, sort, page, pageSize, total, rows, allRows, shopOptions, platformOptions, read,
    initialLoading: computed(() => isMockMode
      ? mockQuery.isPending.value && mockQuery.data.value === undefined
      : realQuery.isPending.value && realQuery.data.value === undefined),
    filterLoading: computed(() => isMockMode
      ? mockQuery.isFetching.value && mockQuery.data.value !== undefined
      : realQuery.isFetching.value && realQuery.data.value !== undefined),
    tableEmptyDescription, readErrorMessage, sortingEnabled: true,
    updateFilters, setSort, setPageSize, retryRead,
  }
}
