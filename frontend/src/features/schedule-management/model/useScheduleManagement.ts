import type { SelectOption } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'

import { type DeviceListFilters, useDeviceListQuery } from '@/entities/device'
import {
  type ScheduleListFilters,
  type ScheduleListItemViewModel,
  type ScheduleSaveInput,
  useCreateScheduleMutation,
  useRemoveScheduleMutation,
  useScheduleDetailQuery,
  useScheduleListQuery,
  useUpdateScheduleMutation,
} from '@/entities/schedule'
import {
  getErrorMessage,
  isInitialQueryError,
  isInitialQueryLoading,
} from '@/shared/api'

import type { ScheduleFilterViewModel } from './types'

function emptyDeviceFilters(): DeviceListFilters {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

export function createDefaultScheduleFilters(): ScheduleFilterViewModel {
  return { enabled: null, deviceId: null, search: '' }
}

function toListFilters(filters: ScheduleFilterViewModel): ScheduleListFilters {
  return { ...filters }
}

export function useScheduleManagement() {
  const message = useMessage()
  const filterDraft = ref(createDefaultScheduleFilters())
  const appliedFilters = ref<ScheduleListFilters>(
    toListFilters(filterDraft.value),
  )
  const page = ref(1)
  const pageSize = ref(10)
  const selectedScheduleId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<'create' | 'edit'>('create')
  const removeVisible = ref(false)
  const runtimeVisible = ref(false)
  const runtimeTaskId = ref<string | null>(null)
  const runtimeDeviceName = ref<string | null>(null)

  const listQuery = useScheduleListQuery(
    computed(() => ({
      page: page.value,
      pageSize: pageSize.value,
      filters: appliedFilters.value,
    })),
  )
  const detailQuery = useScheduleDetailQuery(selectedScheduleId)
  const deviceQuery = useDeviceListQuery(
    computed(() => ({
      page: 1,
      pageSize: 100,
      filters: emptyDeviceFilters(),
    })),
  )
  const createMutation = useCreateScheduleMutation()
  const updateMutation = useUpdateScheduleMutation()
  const removeMutation = useRemoveScheduleMutation()

  const deviceOptions = computed<SelectOption[]>(() =>
    (deviceQuery.data.value?.items ?? []).map((device) => ({
      label: device.enabled
        ? device.deviceName
        : `${device.deviceName}（已停用）`,
      value: device.deviceId,
      disabled: !device.enabled,
    })),
  )
  const rows = computed(() => listQuery.data.value?.items ?? [])
  const listError = computed(() =>
    isInitialQueryError(listQuery.error.value, listQuery.data.value)
      ? getErrorMessage(listQuery.error.value)
      : null,
  )
  const detailError = computed(() =>
    isInitialQueryError(detailQuery.error.value, detailQuery.data.value)
      ? getErrorMessage(detailQuery.error.value)
      : null,
  )

  function query(): void {
    appliedFilters.value = toListFilters(filterDraft.value)
    page.value = 1
  }

  function resetFilters(): void {
    filterDraft.value = createDefaultScheduleFilters()
    appliedFilters.value = toListFilters(filterDraft.value)
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  function openCreate(): void {
    selectedScheduleId.value = null
    formMode.value = 'create'
    formVisible.value = true
  }

  function openDetail(schedule: ScheduleListItemViewModel): void {
    selectedScheduleId.value = schedule.scheduleId
    detailVisible.value = true
  }

  function editSelected(): void {
    if (!selectedScheduleId.value) return
    formMode.value = 'edit'
    formVisible.value = true
  }

  async function save(input: ScheduleSaveInput): Promise<void> {
    try {
      if (formMode.value === 'edit' && selectedScheduleId.value) {
        await updateMutation.mutateAsync({
          scheduleId: selectedScheduleId.value,
          input,
        })
        message.success('定时计划已更新')
      } else {
        const created = await createMutation.mutateAsync(input)
        selectedScheduleId.value = created.scheduleId
        message.success('定时计划已创建')
      }
      formVisible.value = false
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function toggleEnabled(
    schedule: ScheduleListItemViewModel,
  ): Promise<void> {
    try {
      await updateMutation.mutateAsync({
        scheduleId: schedule.scheduleId,
        input: { enabled: !schedule.enabled },
      })
      message.success(schedule.enabled ? '定时计划已停用' : '定时计划已启用')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  function confirmRemove(schedule: ScheduleListItemViewModel): void {
    selectedScheduleId.value = schedule.scheduleId
    removeVisible.value = true
  }

  async function remove(): Promise<void> {
    if (!selectedScheduleId.value) return
    try {
      await removeMutation.mutateAsync(selectedScheduleId.value)
      removeVisible.value = false
      detailVisible.value = false
      message.success('定时计划已移除')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  function openRuntime(taskId: string, deviceName: string): void {
    runtimeTaskId.value = taskId
    runtimeDeviceName.value = deviceName
    runtimeVisible.value = true
  }

  return {
    filterDraft,
    page,
    pageSize,
    selectedScheduleId,
    detailVisible,
    formVisible,
    formMode,
    removeVisible,
    runtimeVisible,
    runtimeTaskId,
    runtimeDeviceName,
    rows,
    total: computed(() => listQuery.data.value?.total ?? 0),
    listLoading: computed(() =>
      isInitialQueryLoading(listQuery.isPending.value, listQuery.data.value),
    ),
    listError,
    refreshing: listQuery.isFetching,
    detail: computed(() => detailQuery.data.value ?? null),
    detailLoading: computed(() =>
      isInitialQueryLoading(
        detailQuery.isPending.value,
        detailQuery.data.value,
      ),
    ),
    detailError,
    deviceOptions,
    deviceOptionsLoading: computed(() =>
      isInitialQueryLoading(
        deviceQuery.isPending.value,
        deviceQuery.data.value,
      ),
    ),
    submitting: computed(
      () => createMutation.isPending.value || updateMutation.isPending.value,
    ),
    removing: removeMutation.isPending,
    query,
    resetFilters,
    setPageSize,
    openCreate,
    openDetail,
    editSelected,
    save,
    toggleEnabled,
    confirmRemove,
    remove,
    openRuntime,
    retryList: listQuery.refetch,
    retryDetail: detailQuery.refetch,
  }
}
