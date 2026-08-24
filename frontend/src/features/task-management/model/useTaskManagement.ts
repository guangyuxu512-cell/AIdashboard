import type { SelectOption } from 'naive-ui'
import dayjs from 'dayjs'
import { computed, ref } from 'vue'

import { type DeviceListFilters, useDeviceListQuery } from '@/entities/device'
import {
  type TaskListFilters,
  type TaskListItemViewModel,
  useTaskListQuery,
} from '@/entities/task'
import {
  getErrorMessage,
  isInitialQueryError,
  isInitialQueryLoading,
} from '@/shared/api'

import type { TaskDatePreset, TaskFilterViewModel } from './types'

export const DEFAULT_TASK_DATE_PRESET: TaskDatePreset = 'last7Days'

export function createDefaultTaskFilters(): TaskFilterViewModel {
  return {
    status: null,
    deviceId: null,
    search: '',
    datePreset: DEFAULT_TASK_DATE_PRESET,
    customDateRange: null,
  }
}

export function resolveTaskListFilters(
  filters: TaskFilterViewModel,
  now: number | Date = Date.now(),
): TaskListFilters {
  const today = dayjs(now).startOf('day')
  let createdFrom: string | null = null
  let createdTo: string | null = null

  if (filters.datePreset === 'today') {
    createdFrom = today.toISOString()
    createdTo = today.add(1, 'day').toISOString()
  } else if (filters.datePreset === 'yesterday') {
    createdFrom = today.subtract(1, 'day').toISOString()
    createdTo = today.toISOString()
  } else if (filters.datePreset === 'last7Days') {
    createdFrom = today.subtract(6, 'day').toISOString()
    createdTo = today.add(1, 'day').toISOString()
  } else if (filters.datePreset === 'last30Days') {
    createdFrom = today.subtract(29, 'day').toISOString()
    createdTo = today.add(1, 'day').toISOString()
  } else if (filters.datePreset === 'custom' && filters.customDateRange) {
    createdFrom = dayjs(filters.customDateRange[0]).startOf('day').toISOString()
    createdTo = dayjs(filters.customDateRange[1])
      .startOf('day')
      .add(1, 'day')
      .toISOString()
  }

  return {
    status: filters.status,
    deviceId: filters.deviceId,
    search: filters.search,
    createdFrom,
    createdTo,
  }
}

function emptyDeviceFilters(): DeviceListFilters {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

export function useTaskManagement() {
  const filterDraft = ref<TaskFilterViewModel>(createDefaultTaskFilters())
  const appliedFilters = ref<TaskListFilters>(
    resolveTaskListFilters(filterDraft.value),
  )
  const page = ref(1)
  const pageSize = ref(10)
  const runtimeTaskId = ref<string | null>(null)
  const runtimeDeviceName = ref<string | null>(null)
  const runtimeVisible = ref(false)

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: appliedFilters.value,
  }))
  const listQuery = useTaskListQuery(listParams)
  const deviceQuery = useDeviceListQuery(
    computed(() => ({
      page: 1,
      pageSize: 100,
      filters: emptyDeviceFilters(),
    })),
  )

  const deviceOptions = computed<SelectOption[]>(() =>
    (deviceQuery.data.value?.items ?? []).map((device) => ({
      label: device.deviceName,
      value: device.deviceId,
    })),
  )
  const rows = computed(() => listQuery.data.value?.items ?? [])
  const listError = computed(() =>
    isInitialQueryError(listQuery.error.value, listQuery.data.value)
      ? getErrorMessage(listQuery.error.value)
      : null,
  )

  function query(): void {
    appliedFilters.value = resolveTaskListFilters(filterDraft.value)
    page.value = 1
  }

  function resetFilters(): void {
    filterDraft.value = createDefaultTaskFilters()
    appliedFilters.value = resolveTaskListFilters(filterDraft.value)
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  function openRuntime(task: TaskListItemViewModel): void {
    runtimeTaskId.value = task.taskId
    runtimeDeviceName.value = task.deviceName
    runtimeVisible.value = true
  }

  return {
    filterDraft,
    page,
    pageSize,
    runtimeTaskId,
    runtimeDeviceName,
    runtimeVisible,
    rows,
    total: computed(() => listQuery.data.value?.total ?? 0),
    listLoading: computed(() =>
      isInitialQueryLoading(listQuery.isPending.value, listQuery.data.value),
    ),
    listError,
    refreshing: listQuery.isFetching,
    deviceOptions,
    deviceOptionsLoading: computed(() =>
      isInitialQueryLoading(
        deviceQuery.isPending.value,
        deviceQuery.data.value,
      ),
    ),
    query,
    resetFilters,
    setPageSize,
    openRuntime,
    retryList: listQuery.refetch,
  }
}
