import { useMessage } from 'naive-ui'
import { useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import {
  deviceDataSource,
  formatRelativeTime,
  type DeviceListFilters,
  type DeviceListItemViewModel,
  type DeviceSaveInput,
  useCreateDeviceMutation,
  useDeviceDetailQuery,
  useDeviceListQuery,
  useDeviceProviderInventoriesQuery,
  useRemoveDeviceMutation,
  useSetDeviceEnabledMutation,
  useUpdateDeviceMutation,
  deviceQueryKeys,
} from '@/entities/device'
import { useCreateTaskMutation, useTaskQuery } from '@/entities/task'
import { getErrorMessage } from '@/shared/api'

import { useDeviceManagementContextQuery } from './device-management-context'
import type {
  DeviceCurrentExecutionViewModel,
  DeviceFilterViewModel,
  DeviceFormMode,
  DeviceFormViewModel,
  DeviceManagementRowViewModel,
  DeviceRecentExecutionViewModel,
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
  const pageSize = ref(10)
  const detailDeviceId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<DeviceFormMode>('create')
  const formInitialValue = ref<DeviceFormViewModel | null>(null)
  const editingDeviceId = ref<string | null>(null)
  const applicationsVisible = ref(false)
  const selectedDeviceIds = ref<string[]>([])
  const statusChangingDeviceId = ref<string | null>(null)
  const removeDevice = ref<DeviceListItemViewModel | null>(null)
  const removeVisible = ref(false)
  const refreshTaskId = ref<string | null>(null)
  const handledRefreshTaskId = ref<string | null>(null)
  const queryClient = useQueryClient()

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: {
      ...appliedFilters.value,
      keyword: filterDraft.value.keyword,
    },
  }))
  const listQuery = useDeviceListQuery(listParams)
  const baseRows = computed(() => listQuery.data.value?.items ?? [])
  const deviceIds = computed(() =>
    baseRows.value.map((device) => device.deviceId),
  )
  const managementContextQuery = useDeviceManagementContextQuery(deviceIds)
  const detailQuery = useDeviceDetailQuery(detailDeviceId)
  const providerInventoryQuery =
    useDeviceProviderInventoriesQuery(detailDeviceId)
  const refreshTaskQuery = useTaskQuery(refreshTaskId)
  const createTaskMutation = useCreateTaskMutation()
  const createMutation = useCreateDeviceMutation()
  const updateMutation = useUpdateDeviceMutation()
  const setEnabledMutation = useSetDeviceEnabledMutation()
  const removeMutation = useRemoveDeviceMutation()

  function getCurrentExecution(
    device: DeviceListItemViewModel,
  ): DeviceCurrentExecutionViewModel {
    const refreshTask = refreshTaskQuery.data.value
    if (
      refreshTask?.target_device_id === device.deviceId &&
      (refreshTask.status === 'pending' || refreshTask.status === 'running')
    ) {
      return {
        status: refreshTask.status,
        label: refreshTask.status === 'pending' ? '待执行' : '执行中',
        name: refreshTask.skill_id,
        tone: refreshTask.status === 'pending' ? 'warning' : 'info',
      }
    }
    if (device.dataSource === 'real') {
      return { status: 'unknown', label: '—', name: null, tone: 'neutral' }
    }
    if (device.runtimeStatus === 'busy') {
      return {
        status: 'running',
        label: '执行中',
        name: device.currentTaskName,
        tone: 'info',
      }
    }
    if (device.currentTaskName) {
      return {
        status: 'pending',
        label: '待执行',
        name: device.currentTaskName,
        tone: 'warning',
      }
    }
    return { status: 'idle', label: '空闲', name: null, tone: 'neutral' }
  }

  const rows = computed<DeviceManagementRowViewModel[]>(() => {
    const context = managementContextQuery.data.value
    return baseRows.value.map((device) => ({
      ...device,
      currentExecution: getCurrentExecution(device),
      yingdaoInventory: context?.inventories[device.deviceId] ?? null,
      boundShopCount: context?.bindingCounts[device.deviceId] ?? null,
    }))
  })
  const visibleRows = computed(() => {
    const keyword = filterDraft.value.keyword.trim().toLocaleLowerCase()
    if (!keyword) return rows.value
    return rows.value.filter((device) =>
      [
        device.deviceName,
        device.location,
        device.yingdaoInventory?.accountDisplay ?? '',
      ].some((value) => value.toLocaleLowerCase().includes(keyword)),
    )
  })
  const total = computed(() => listQuery.data.value?.total ?? 0)
  const statistics = computed(() => ({
    total: total.value,
    online: rows.value.filter((device) =>
      ['online', 'busy'].includes(device.runtimeStatus),
    ).length,
    offline: rows.value.filter((device) =>
      ['offline', 'unavailable'].includes(device.runtimeStatus),
    ).length,
    error: rows.value.filter((device) => device.runtimeStatus === 'error')
      .length,
  }))
  const listError = computed(() =>
    listQuery.error.value && !listQuery.data.value
      ? getErrorMessage(listQuery.error.value)
      : null,
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
  const detailRow = computed(
    () =>
      rows.value.find((device) => device.deviceId === detailDeviceId.value) ??
      null,
  )
  const detailCurrentExecution = computed(() =>
    detailQuery.data.value
      ? getCurrentExecution(detailQuery.data.value)
      : (detailRow.value?.currentExecution ?? null),
  )
  const detailBoundShopCount = computed(
    () => detailRow.value?.boundShopCount ?? null,
  )
  const recentExecutions = computed<DeviceRecentExecutionViewModel[]>(() => {
    const task = refreshTaskQuery.data.value
    if (
      !task ||
      task.target_device_id !== detailDeviceId.value ||
      !['success', 'failed', 'lost'].includes(task.status)
    ) {
      return []
    }
    const status = task.status as 'success' | 'failed' | 'lost'
    return [
      {
        id: task.task_id,
        name: task.skill_id,
        status,
        statusLabel:
          status === 'success'
            ? '成功'
            : status === 'failed'
              ? '失败'
              : '丢失 / 中断',
        tone:
          status === 'success'
            ? 'success'
            : status === 'failed'
              ? 'error'
              : 'warning',
        timeDisplay: formatRelativeTime(task.finished_at ?? task.updated_at),
      },
    ]
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

  async function refreshList(): Promise<void> {
    await Promise.all([listQuery.refetch(), managementContextQuery.refetch()])
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
    () => filterDraft.value.keyword,
    () => {
      page.value = 1
    },
  )

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
        await queryClient.invalidateQueries({
          queryKey: ['devices', 'management-context'],
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

  async function toggleEnabled(device: DeviceListItemViewModel): Promise<void> {
    statusChangingDeviceId.value = device.deviceId
    try {
      await setEnabledMutation.mutateAsync({
        deviceId: device.deviceId,
        enabled: !device.enabled,
      })
      message.success(device.enabled ? '设备已停用' : '设备已启用')
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      statusChangingDeviceId.value = null
    }
  }

  function requestRemove(device: DeviceListItemViewModel): void {
    removeDevice.value = device
    removeVisible.value = true
  }

  async function confirmRemove(): Promise<void> {
    const device = removeDevice.value
    if (!device) return
    try {
      await removeMutation.mutateAsync(device.deviceId)
      selectedDeviceIds.value = selectedDeviceIds.value.filter(
        (deviceId) => deviceId !== device.deviceId,
      )
      if (detailDeviceId.value === device.deviceId) {
        detailVisible.value = false
        detailDeviceId.value = null
      }
      removeVisible.value = false
      removeDevice.value = null
      if (visibleRows.value.length === 1 && page.value > 1) page.value -= 1
      message.success('设备已移除')
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
    visibleRows,
    selectedDeviceIds,
    statusChangingDeviceId,
    removeDevice,
    removeVisible,
    total,
    statistics,
    refreshing: computed(
      () =>
        listQuery.isFetching.value || managementContextQuery.isFetching.value,
    ),
    listLoading: listQuery.isPending,
    listError,
    detailDevice: computed(() => detailQuery.data.value ?? null),
    detailCurrentExecution,
    detailBoundShopCount,
    recentExecutions,
    detailLoading: detailQuery.isPending,
    detailError,
    yingdaoInventory: computed(() => providerInventoryQuery.data.value ?? null),
    providerInventoryLoading: providerInventoryQuery.isPending,
    providerInventoryError,
    yingdaoRefreshing,
    formSubmitting,
    removeSubmitting: computed(() => removeMutation.isPending.value),
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    refreshList,
    retryDetail: detailQuery.refetch,
    retryProviderInventory: providerInventoryQuery.refetch,
    openDetail,
    openCreate,
    openEdit,
    openYingdaoApplications,
    refreshYingdao,
    saveDevice,
    toggleEnabled,
    requestRemove,
    confirmRemove,
  }
}
