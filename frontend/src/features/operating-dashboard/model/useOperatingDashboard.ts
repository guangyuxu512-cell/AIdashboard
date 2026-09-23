import { keepPreviousData, useMutation, useQuery } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import type { SelectOption } from 'naive-ui'

import { getPlatformDefinition } from '@/entities/platform'
import { apiMode, getErrorMessage } from '@/shared/api'

import {
  operatingDashboardApi,
  type OperatingDashboardCollectionJobDto,
  type OperatingDashboardCollectionSubmission,
} from '../api/operating-dashboard-api'
import {
  resolveOperatingDashboardDateRange,
  sortOperatingDashboardRows,
} from './dashboard'
import { createOperatingDashboardMockSource } from './mock-source'
import type {
  OperatingDashboardFilters,
  OperatingDashboardRefreshResult,
  OperatingDashboardSort,
  OperatingDashboardTableRow,
} from './types'

export interface OperatingDashboardRefreshFeedback {
  tone: 'success' | 'warning' | 'error'
  message: string
}

type DashboardRefreshMode = 'fill_gaps' | 'recollect'

interface DashboardRefreshRequest {
  filters: OperatingDashboardFilters
  mode: DashboardRefreshMode
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
      ? ([...filters.customDateRange] as [number, number])
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

function getMockFeedback(
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

function isActiveCollection(job: OperatingDashboardCollectionJobDto): boolean {
  return (
    (job.status === 'pending' || job.status === 'running') &&
    job.counts.pending + job.counts.running > 0
  )
}

function getCollectionFeedback(
  job: OperatingDashboardCollectionJobDto,
): OperatingDashboardRefreshFeedback {
  const { counts } = job
  if (counts.paused_reauthorization > 0) {
    const activeCount = counts.pending + counts.running
    return {
      tone: 'warning',
      message:
        activeCount > 0
          ? `其中 ${counts.paused_reauthorization} 条需重新授权，另有 ${activeCount} 条正在处理中。`
          : `其中 ${counts.paused_reauthorization} 条需重新授权后才能继续更新。`,
    }
  }
  if (isActiveCollection(job)) {
    return {
      tone: 'warning',
      message: `已提交更新：${counts.pending + counts.running} 条店铺日期数据正在处理中。`,
    }
  }
  if (counts.failed > 0) {
    return {
      tone: job.status === 'failed' ? 'error' : 'warning',
      message: `更新已结束：成功 ${counts.succeeded} 条，失败 ${counts.failed} 条，跳过 ${counts.skipped} 条。`,
    }
  }
  if (counts.skipped > 0) {
    return {
      tone: 'warning',
      message: `更新已结束：成功 ${counts.succeeded} 条，跳过 ${counts.skipped} 条。`,
    }
  }
  return {
    tone: 'success',
    message: `已完成 ${counts.succeeded} 条店铺日期数据更新。`,
  }
}

function getCollectionSubmissionFeedback(
  submission: OperatingDashboardCollectionSubmission,
): OperatingDashboardRefreshFeedback {
  if (submission.state === 'up_to_date') {
    return { tone: 'success', message: submission.message }
  }
  if (submission.state === 'unsupported') {
    return { tone: 'warning', message: submission.message }
  }
  if (submission.state === 'attention_required') {
    return {
      tone: 'warning',
      message:
        submission.blockedShopDays > 0
          ? `${submission.message}（${submission.blockedShopDays} 个店铺日期）`
          : submission.message,
    }
  }
  const parts: string[] = []
  if (submission.queuedShopDays > 0) {
    parts.push(`已安排 ${submission.queuedShopDays} 个店铺日期`)
  }
  if (submission.activeShopDays > 0) {
    parts.push(`${submission.activeShopDays} 个店铺日期正在处理中`)
  }
  if (submission.blockedShopDays > 0) {
    parts.push(`${submission.blockedShopDays} 个店铺日期暂不能自动补采`)
  }
  return {
    tone: submission.blockedShopDays > 0 ? 'warning' : 'success',
    message:
      parts.length > 0
        ? `${submission.message}：${parts.join('；')}。`
        : submission.message,
  }
}

/**
 * Coordinates the two explicitly separate dashboard sources. Mock mode owns
 * its fixture and client-side full-result sort; real mode only consumes the
 * formal Backend read/update contract, which sorts before pagination.
 */
export function useOperatingDashboard() {
  const filters = ref<OperatingDashboardFilters>(cloneFilters(DEFAULT_FILTERS))
  const sort = ref<OperatingDashboardSort | null>(null)
  const page = ref(1)
  const pageSize = ref(10)
  const refreshFeedback = ref<OperatingDashboardRefreshFeedback | null>(null)
  const collectionJobId = ref<string | null>(null)
  const collectionScope = ref<OperatingDashboardFilters | null>(null)
  const settledCollectionJobId = ref<string | null>(null)
  const isMockMode = apiMode === 'mock'
  const mockSource = isMockMode ? createOperatingDashboardMockSource() : null
  const dateRange = computed(() =>
    resolveOperatingDashboardDateRange(filters.value),
  )

  const mockQuery = useQuery({
    queryKey: computed(() => [
      'operating-dashboard',
      'mock',
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

  const realQuery = useQuery({
    queryKey: computed(() => [
      'operating-dashboard',
      'real',
      dateRange.value.startDate,
      dateRange.value.endDate,
      filters.value.platform,
      filters.value.shopId,
      sort.value?.field ?? null,
      sort.value?.direction ?? null,
      page.value,
      pageSize.value,
    ]),
    queryFn: () =>
      operatingDashboardApi.read({
        range: dateRange.value,
        filters: cloneFilters(filters.value),
        sort: sort.value,
        page: page.value,
        pageSize: pageSize.value,
      }),
    enabled: !isMockMode,
    placeholderData: keepPreviousData,
    retry: false,
  })

  const collectionJobQuery = useQuery({
    queryKey: computed(() => [
      'operating-dashboard',
      'collection',
      collectionJobId.value,
    ]),
    queryFn: () => operatingDashboardApi.getCollection(collectionJobId.value!),
    enabled: computed(() => !isMockMode && collectionJobId.value !== null),
    retry: false,
    refetchInterval: (query) => {
      const job = query.state.data
      return job && isActiveCollection(job) ? 1_000 : false
    },
  })

  const mockRefreshMutation = useMutation({
    mutationFn: (requestFilters: OperatingDashboardFilters) =>
      mockSource!.refresh(requestFilters),
    onSuccess: async (result, requestFilters) => {
      if (!sameFilters(requestFilters, filters.value)) return
      refreshFeedback.value = getMockFeedback(result)
      await mockQuery.refetch()
    },
    onError: (error, requestFilters) => {
      if (!sameFilters(requestFilters, filters.value)) return
      refreshFeedback.value = { tone: 'error', message: getErrorMessage(error) }
    },
  })

  const realRefreshMutation = useMutation({
    mutationFn: (request: DashboardRefreshRequest) =>
      operatingDashboardApi.requestCollectionUpdate({
        range: resolveOperatingDashboardDateRange(request.filters),
        filters: request.filters,
        forceRecollect: request.mode === 'recollect',
      }),
    onSuccess: (submission, request) => {
      const requestFilters = request.filters
      const job = submission.collectionJob
      if (job) {
        collectionJobId.value = job.collection_job_id
        collectionScope.value = cloneFilters(requestFilters)
        settledCollectionJobId.value = null
      }
      if (sameFilters(requestFilters, filters.value)) {
        refreshFeedback.value = getCollectionSubmissionFeedback(submission)
        // A gap check that finds no work still reads the authoritative
        // persisted result. It never waits for or fabricates a collection Job.
        if (!job) void realQuery.refetch()
      }
    },
    onError: (error, request) => {
      const requestFilters = request.filters
      if (!sameFilters(requestFilters, filters.value)) return
      refreshFeedback.value = { tone: 'error', message: getErrorMessage(error) }
    },
  })

  watch(
    () => collectionJobQuery.data.value,
    (job) => {
      if (!job || !collectionScope.value) return
      if (sameFilters(collectionScope.value, filters.value)) {
        refreshFeedback.value = getCollectionFeedback(job)
      }
      if (
        !isActiveCollection(job) &&
        settledCollectionJobId.value !== job.collection_job_id
      ) {
        settledCollectionJobId.value = job.collection_job_id
        void realQuery.refetch()
      }
    },
  )

  watch(
    () => collectionJobQuery.error.value,
    (error) => {
      if (!error || !collectionScope.value) return
      if (!sameFilters(collectionScope.value, filters.value)) return
      refreshFeedback.value = {
        tone: 'error',
        message: `更新进度读取失败：${getErrorMessage(error)}`,
      }
    },
  )

  const read = computed(() =>
    isMockMode ? mockQuery.data.value : realQuery.data.value,
  )
  const allRows = computed<OperatingDashboardTableRow[]>(
    () => read.value?.tableRows ?? [],
  )
  const sortedRows = computed<OperatingDashboardTableRow[]>(() =>
    isMockMode
      ? sortOperatingDashboardRows(allRows.value, sort.value)
      : allRows.value,
  )
  const total = computed(() =>
    isMockMode ? sortedRows.value.length : (read.value?.tablePage.total ?? 0),
  )
  const pageCount = computed(() =>
    Math.max(1, Math.ceil(total.value / pageSize.value)),
  )
  const rows = computed(() => {
    if (!isMockMode) return sortedRows.value
    const start = (page.value - 1) * pageSize.value
    return sortedRows.value.slice(start, start + pageSize.value)
  })
  const shopOptions = computed<SelectOption[]>(() =>
    (read.value?.allAvailableShops ?? [])
      .filter(
        (shop) =>
          filters.value.platform === null ||
          shop.platform === filters.value.platform,
      )
      .map((shop) => ({ label: shop.shopName, value: shop.shopId })),
  )
  const platformOptions = computed<SelectOption[]>(() => {
    const platforms = new Set(
      (read.value?.allAvailableShops ?? []).map((shop) => shop.platform),
    )
    return [...platforms].flatMap((platform) => {
      const definition = getPlatformDefinition(platform)
      return definition
        ? [{ label: definition.label, value: definition.code }]
        : []
    })
  })
  const activeCollection = computed(() => {
    const job = collectionJobQuery.data.value
    return Boolean(
      job &&
      !collectionJobQuery.isError.value &&
      collectionScope.value &&
      sameFilters(collectionScope.value, filters.value) &&
      isActiveCollection(job),
    )
  })
  const refreshing = computed(() =>
    isMockMode
      ? mockRefreshMutation.isPending.value
      : realRefreshMutation.isPending.value || activeCollection.value,
  )
  const tableEmptyDescription = computed(() => {
    if (!isMockMode && realQuery.isError.value)
      return '经营数据读取失败，请重试'
    return '当前筛选范围暂无经营数据'
  })
  const readErrorMessage = computed(() =>
    !isMockMode && realQuery.error.value
      ? getErrorMessage(realQuery.error.value)
      : '经营数据暂不可用',
  )

  watch(pageCount, (nextPageCount) => {
    if (page.value > nextPageCount) page.value = nextPageCount
  })

  function updateFilters(next: OperatingDashboardFilters): void {
    const knownShops = read.value?.allAvailableShops ?? []
    const currentShopExists =
      next.shopId === null ||
      knownShops.length === 0 ||
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

  function setSort(value: OperatingDashboardSort | null): void {
    sort.value = value
    page.value = 1
  }

  function refresh(mode: DashboardRefreshMode = 'fill_gaps'): void {
    if (refreshing.value) return
    const requestFilters = cloneFilters(filters.value)
    if (isMockMode) {
      mockRefreshMutation.mutate(requestFilters)
      return
    }
    realRefreshMutation.mutate({ filters: requestFilters, mode })
  }

  function retryRead(): void {
    if (!isMockMode) void realQuery.refetch()
  }

  return {
    apiMode,
    filters,
    sort,
    page,
    pageSize,
    total,
    rows,
    allRows,
    shopOptions,
    platformOptions,
    read,
    initialLoading: computed(() =>
      isMockMode
        ? mockQuery.isPending.value && mockQuery.data.value === undefined
        : realQuery.isPending.value && realQuery.data.value === undefined,
    ),
    filterLoading: computed(() =>
      isMockMode
        ? mockQuery.isFetching.value && mockQuery.data.value !== undefined
        : realQuery.isFetching.value && realQuery.data.value !== undefined,
    ),
    tableEmptyDescription,
    readErrorMessage,
    refreshFeedback,
    refreshing,
    refreshAvailable: computed(
      () => isMockMode || read.value?.collectionAvailable === true,
    ),
    sortingEnabled: true,
    updateFilters,
    setSort,
    setPageSize,
    refresh,
    recollect: () => refresh('recollect'),
    retryRead,
  }
}
