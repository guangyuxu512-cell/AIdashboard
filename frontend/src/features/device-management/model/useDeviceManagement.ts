import { useMessage } from 'naive-ui'
import { useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import {
  deviceDataSource,
  type DeviceListFilters,
  type DeviceListItemViewModel,
  type DeviceSaveInput,
  useCreateDeviceMutation,
  useDeviceDetailQuery,
  useDeviceListQuery,
  useDeviceProviderInventoriesQuery,
  useUpdateDeviceMutation,
  deviceQueryKeys,
} from '@/entities/device'
import { useCreateTaskMutation, useTaskQuery } from '@/entities/task'
import { getErrorMessage } from '@/shared/api'

import type {
  DeviceFilterViewModel,
  DeviceFormMode,
  DeviceFormViewModel,
} from './types'

function createEmptyFilters(): DeviceFilterViewModel {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

export function useDeviceManagement() {
  const message = useMessage()
  const filterDraft = ref<DeviceFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<DeviceListFilters>(createEmptyFilters())
  const page = ref(1)
  const pageSize = ref(9)
  const detailDeviceId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<DeviceFormMode>('create')
  const formInitialValue = ref<DeviceFormViewModel | null>(null)
  const editingDeviceId = ref<string | null>(null)
  const applicationsVisible = ref(false)
  const refreshTaskId = ref<string | null>(null)
  const handledRefreshTaskId = ref<string | null>(null)
  const queryClient = useQueryClient()

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: appliedFilters.value,
  }))
  const listQuery = useDeviceListQuery(listParams)
  const detailQuery = useDeviceDetailQuery(detailDeviceId)
  const providerInventoryQuery = useDeviceProviderInventoriesQuery(detailDeviceId)
  const refreshTaskQuery = useTaskQuery(refreshTaskId)
  const createTaskMutation = useCreateTaskMutation()
  const createMutation = useCreateDeviceMutation()
  const updateMutation = useUpdateDeviceMutation()

  const rows = computed(() => listQuery.data.value?.items ?? [])
  const total = computed(() => listQuery.data.value?.total ?? 0)
  const statistics = computed(() => ({
    total: total.value,
    online: rows.value.filter((device) =>
      ['online', 'busy'].includes(device.runtimeStatus),
    ).length,
    offline: rows.value.filter((device) =>
      ['offline', 'unavailable', 'error'].includes(device.runtimeStatus),
    ).length,
  }))
  const listError = computed(() =>
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )
  const detailError = computed(() =>
    detailQuery.error.value ? getErrorMessage(detailQuery.error.value) : null,
  )
  const providerInventoryError = computed(() =>
    providerInventoryQuery.error.value
      ? getErrorMessage(providerInventoryQuery.error.value)
      : null,
  )
  const yingdaoRefreshing = computed(
    () =>
      createTaskMutation.isPending.value ||
      refreshTaskQuery.data.value?.status === 'pending' ||
      refreshTaskQuery.data.value?.status === 'running',
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

  function openDetail(device: DeviceListItemViewModel): void {
    detailDeviceId.value = device.deviceId
    detailVisible.value = true
  }

  async function refreshYingdao(): Promise<void> {
    if (!detailDeviceId.value || deviceDataSource.mode !== 'real') return
    try {
      const task = await createTaskMutation.mutateAsync({
        target_device_id: detailDeviceId.value,
        skill_id: 'yingdao.discover',
        input: {},
      })
      handledRefreshTaskId.value = null
      refreshTaskId.value = task.task_id
      message.info('已创建影刀能力刷新任务')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  function openYingdaoApplications(): void {
    applicationsVisible.value = true
  }

  watch(
    () => refreshTaskQuery.data.value,
    async (task) => {
      if (
        !task ||
        task.task_id === handledRefreshTaskId.value ||
        !['success', 'failed', 'lost'].includes(task.status)
      ) {
        return
      }
      handledRefreshTaskId.value = task.task_id
      if (task.status === 'success') {
        await queryClient.invalidateQueries({
          queryKey: deviceQueryKeys.providerInventories(task.target_device_id),
        })
        message.success('影刀能力已刷新')
        return
      }
      message.error(
        task.error_message ??
          (task.status === 'lost' ? '刷新任务已失联' : '影刀能力刷新失败'),
      )
    },
  )

  function openCreate(): void {
    formMode.value = 'create'
    editingDeviceId.value = null
    formInitialValue.value = null
    formVisible.value = true
  }

  function openEdit(device: DeviceListItemViewModel): void {
    formMode.value = 'edit'
    editingDeviceId.value = device.deviceId
    formInitialValue.value = {
      deviceName: device.deviceName,
      enabled: device.enabled,
      location: device.location === '未设置' ? '' : device.location,
      note: device.note,
    }
    formVisible.value = true
  }

  async function saveDevice(form: DeviceFormViewModel): Promise<void> {
    const input: DeviceSaveInput = { ...form }
    try {
      if (formMode.value === 'edit' && editingDeviceId.value) {
        await updateMutation.mutateAsync({
          deviceId: editingDeviceId.value,
          input,
        })
        message.success('设备记录已更新')
      } else {
        await createMutation.mutateAsync(input)
        message.success('设备基础记录已创建')
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
    applicationsVisible,
    formVisible,
    formMode,
    formInitialValue,
    rows,
    total,
    statistics,
    filtersAvailable: deviceDataSource.supportsFilters,
    dataSourceDescription:
      deviceDataSource.mode === 'real'
        ? '数据来自 FastAPI；Worker在线状态与影刀环境来自目标设备。'
        : '当前运行、资源与心跳信息来自 Frontend Fixture。',
    listLoading: listQuery.isPending,
    listError,
    detailDevice: computed(() => detailQuery.data.value ?? null),
    detailLoading: detailQuery.isPending,
    detailError,
    yingdaoInventory: computed(() => providerInventoryQuery.data.value ?? null),
    providerInventoryLoading: computed(
      () =>
        deviceDataSource.mode === 'real' &&
        providerInventoryQuery.isPending.value,
    ),
    providerInventoryError,
    yingdaoRefreshing,
    formSubmitting,
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    retryDetail: detailQuery.refetch,
    retryProviderInventory: providerInventoryQuery.refetch,
    openDetail,
    openCreate,
    openEdit,
    openYingdaoApplications,
    refreshYingdao,
    saveDevice,
  }
}
