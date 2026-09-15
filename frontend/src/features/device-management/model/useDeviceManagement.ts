import { useMessage } from 'naive-ui'
import { useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import {
  deviceDataSource,
  deviceApi,
  formatRelativeTime,
  type DeviceListFilters,
  type DeviceListItemViewModel,
  type DeviceSaveInput,
  type ProviderApplicationViewModel,
  useCreateDeviceMutation,
  useDeviceDetailQuery,
  useDeviceListQuery,
  useDeviceProviderInventoriesQuery,
  useDeviceSkillCapabilitiesQuery,
  useDeviceWorkerCredentialQuery,
  useRemoveDeviceMutation,
  useSetDeviceEnabledMutation,
  useUpdateDeviceMutation,
  deviceQueryKeys,
} from '@/entities/device'
import {
  useActiveTasksQuery,
  useCreateTaskMutation,
  useTaskQuery,
} from '@/entities/task'
import { apiMode } from '@/shared/api'
import { getErrorMessage } from '@/shared/api'

import { useDeviceManagementContextQuery } from './device-management-context'
import { resolveDeviceCurrentExecution } from './device-current-execution'
import {
  isInitialQueryError,
  isInitialQueryLoading,
} from './device-capability-state'
import type {
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
  const capabilityDeviceId = ref<string | null>(null)
  const capabilityVisible = ref(false)
  const applicationRunVisible = ref(false)
  const selectedApplication = ref<ProviderApplicationViewModel | null>(null)
  const selectedDeviceIds = ref<string[]>([])
  const statusChangingDeviceId = ref<string | null>(null)
  const removeDevice = ref<DeviceListItemViewModel | null>(null)
  const removeVisible = ref(false)
  const credentialAction = ref<'rotate' | 'revoke' | null>(null)
  const credentialConfirmVisible = ref(false)
  const workerTokenVisible = ref(false)
  const oneTimeWorkerToken = ref<string | null>(null)
  const workerCredentialSubmitting = ref(false)
  const refreshTaskId = ref<string | null>(null)
  const runtimeTaskId = ref<string | null>(null)
  const runtimeVisible = ref(false)
  const handledRefreshTaskId = ref<string | null>(null)
  const queryClient = useQueryClient()

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: {
      ...appliedFilters.value,
    },
  }))
  const listQuery = useDeviceListQuery(listParams)
  const baseRows = computed(() => listQuery.data.value?.items ?? [])
  const deviceIds = computed(() =>
    baseRows.value.map((device) => device.deviceId),
  )
  const managementContextQuery = useDeviceManagementContextQuery(deviceIds)
  const activeTasksQuery = useActiveTasksQuery(
    deviceIds,
    computed(() => apiMode === 'real'),
  )
  const detailQuery = useDeviceDetailQuery(detailDeviceId)
  const workerCredentialQuery = useDeviceWorkerCredentialQuery(
    detailDeviceId,
    computed(() => apiMode === 'real'),
  )
  const providerInventoryQuery =
    useDeviceProviderInventoriesQuery(detailDeviceId)
  const capabilityProviderInventoryQuery =
    useDeviceProviderInventoriesQuery(capabilityDeviceId)
  const skillCapabilitiesQuery =
    useDeviceSkillCapabilitiesQuery(capabilityDeviceId)
  const refreshTaskQuery = useTaskQuery(refreshTaskId)
  const createTaskMutation = useCreateTaskMutation()
  const createMutation = useCreateDeviceMutation()
  const updateMutation = useUpdateDeviceMutation()
  const setEnabledMutation = useSetDeviceEnabledMutation()
  const removeMutation = useRemoveDeviceMutation()

  const rows = computed<DeviceManagementRowViewModel[]>(() => {
    const context = managementContextQuery.data.value
    const activeTasks = activeTasksQuery.data.value ?? {}
    return baseRows.value.map((device) => ({
      ...device,
      currentExecution: resolveDeviceCurrentExecution(
        device,
        activeTasks[device.deviceId] ?? null,
        refreshTaskQuery.data.value ?? null,
      ),
      yingdaoInventory: context?.inventories[device.deviceId] ?? null,
      boundShopCount: context?.bindingCounts[device.deviceId] ?? null,
      activeTask: activeTasks[device.deviceId] ?? null,
    }))
  })
  const visibleRows = computed(() => rows.value)
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
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )
  const detailError = computed(() =>
    detailQuery.error.value ? getErrorMessage(detailQuery.error.value) : null,
  )
  const providerInventoryError = computed(() =>
    isInitialQueryError(
      providerInventoryQuery.error.value,
      providerInventoryQuery.data.value,
    )
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
      ? resolveDeviceCurrentExecution(
          detailQuery.data.value,
          activeTasksQuery.data.value?.[detailQuery.data.value.deviceId] ??
            null,
          refreshTaskQuery.data.value ?? null,
        )
      : (detailRow.value?.currentExecution ?? null),
  )
  const runtimeDeviceName = computed(
    () =>
      rows.value.find(
        (device) => device.currentExecution.taskId === runtimeTaskId.value,
      )?.deviceName ?? null,
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
    const deviceId = capabilityVisible.value
      ? capabilityDeviceId.value
      : detailDeviceId.value
    if (!deviceId || deviceDataSource.mode !== 'real') return
    try {
      const task = await createTaskMutation.mutateAsync({
        target_device_id: deviceId,
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

  function openCapabilities(device: DeviceListItemViewModel): void {
    capabilityDeviceId.value = device.deviceId
    capabilityVisible.value = true
    detailVisible.value = false
  }

  function runYingdaoApplication(
    application: ProviderApplicationViewModel,
  ): void {
    selectedApplication.value = application
    applicationRunVisible.value = true
  }

  function openTaskRuntime(taskId: string): void {
    runtimeTaskId.value = taskId
    runtimeVisible.value = true
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
        await queryClient.invalidateQueries({
          queryKey: ['devices', 'management-context'],
        })
        await queryClient.invalidateQueries({
          queryKey: [
            'automation-app-configs',
            'yingdao',
            'applications',
          ],
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
      if (capabilityDeviceId.value === device.deviceId) {
        capabilityVisible.value = false
        capabilityDeviceId.value = null
      }
      removeVisible.value = false
      removeDevice.value = null
      if (visibleRows.value.length === 1 && page.value > 1) page.value -= 1
      message.success('设备已移除')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function issueWorkerCredential(): Promise<void> {
    const deviceId = detailDeviceId.value
    if (!deviceId || apiMode !== 'real') return
    workerCredentialSubmitting.value = true
    try {
      const issued = await deviceApi.issueWorkerCredential(deviceId)
      oneTimeWorkerToken.value = issued.token
      workerTokenVisible.value = true
      await workerCredentialQuery.refetch()
      message.success('Worker Token 已签发')
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      workerCredentialSubmitting.value = false
    }
  }

  function requestWorkerCredentialAction(action: 'rotate' | 'revoke'): void {
    credentialAction.value = action
    credentialConfirmVisible.value = true
  }

  async function confirmWorkerCredentialAction(): Promise<void> {
    const deviceId = detailDeviceId.value
    const action = credentialAction.value
    if (!deviceId || !action || apiMode !== 'real') return
    workerCredentialSubmitting.value = true
    try {
      if (action === 'rotate') {
        const issued = await deviceApi.rotateWorkerCredential(deviceId)
        oneTimeWorkerToken.value = issued.token
        workerTokenVisible.value = true
        message.success('Worker Token 已轮换，旧 Token 已失效')
      } else {
        await deviceApi.revokeWorkerCredential(deviceId)
        message.success('Worker 凭证已撤销')
      }
      credentialConfirmVisible.value = false
      credentialAction.value = null
      await workerCredentialQuery.refetch()
    } catch (error) {
      message.error(getErrorMessage(error))
    } finally {
      workerCredentialSubmitting.value = false
    }
  }

  function setWorkerTokenVisible(value: boolean): void {
    workerTokenVisible.value = value
    if (!value) oneTimeWorkerToken.value = null
  }

  return {
    filterDraft,
    page,
    pageSize,
    detailVisible,
    runtimeVisible,
    runtimeTaskId,
    runtimeDeviceName,
    capabilityVisible,
    capabilityDeviceId,
    applicationRunVisible,
    selectedApplication,
    detailDeviceId,
    formVisible,
    formMode,
    formInitialValue,
    rows,
    visibleRows,
    selectedDeviceIds,
    statusChangingDeviceId,
    removeDevice,
    removeVisible,
    credentialAction,
    credentialConfirmVisible,
    workerTokenVisible,
    oneTimeWorkerToken,
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
    workerCredential: computed(
      () => workerCredentialQuery.data.value ?? null,
    ),
    workerCredentialLoading: computed(() =>
      isInitialQueryLoading(
        workerCredentialQuery.isPending.value,
        workerCredentialQuery.data.value,
      ),
    ),
    workerCredentialError: computed(() =>
      isInitialQueryError(
        workerCredentialQuery.error.value,
        workerCredentialQuery.data.value,
      )
        ? getErrorMessage(workerCredentialQuery.error.value)
        : null,
    ),
    workerCredentialSubmitting,
    yingdaoInventory: computed(() => providerInventoryQuery.data.value ?? null),
    providerInventoryLoading: computed(() =>
      isInitialQueryLoading(
        providerInventoryQuery.isPending.value,
        providerInventoryQuery.data.value,
      ),
    ),
    providerInventoryError,
    capabilityDevice: computed(
      () =>
        rows.value.find(
          (device) => device.deviceId === capabilityDeviceId.value,
        ) ?? null,
    ),
    skillCapabilities: computed(
      () => skillCapabilitiesQuery.data.value ?? [],
    ),
    skillCapabilitiesLoading: computed(() =>
      isInitialQueryLoading(
        skillCapabilitiesQuery.isPending.value,
        skillCapabilitiesQuery.data.value,
      ),
    ),
    skillCapabilitiesError: computed(() =>
      isInitialQueryError(
        skillCapabilitiesQuery.error.value,
        skillCapabilitiesQuery.data.value,
      )
        ? getErrorMessage(skillCapabilitiesQuery.error.value)
        : null,
    ),
    capabilityYingdaoInventory: computed(
      () => capabilityProviderInventoryQuery.data.value ?? null,
    ),
    capabilityProviderInventoryLoading: computed(() =>
      isInitialQueryLoading(
        capabilityProviderInventoryQuery.isPending.value,
        capabilityProviderInventoryQuery.data.value,
      ),
    ),
    capabilityProviderInventoryError: computed(() =>
      isInitialQueryError(
        capabilityProviderInventoryQuery.error.value,
        capabilityProviderInventoryQuery.data.value,
      )
        ? getErrorMessage(capabilityProviderInventoryQuery.error.value)
        : null,
    ),
    yingdaoRefreshing,
    formSubmitting,
    removeSubmitting: computed(() => removeMutation.isPending.value),
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    refreshList,
    retryDetail: detailQuery.refetch,
    retryWorkerCredential: workerCredentialQuery.refetch,
    retryProviderInventory: providerInventoryQuery.refetch,
    retrySkillCapabilities: skillCapabilitiesQuery.refetch,
    retryCapabilityProviderInventory:
      capabilityProviderInventoryQuery.refetch,
    openDetail,
    openCreate,
    openEdit,
    openCapabilities,
    runYingdaoApplication,
    openTaskRuntime,
    refreshYingdao,
    saveDevice,
    toggleEnabled,
    requestRemove,
    confirmRemove,
    issueWorkerCredential,
    requestWorkerCredentialAction,
    confirmWorkerCredentialAction,
    setWorkerTokenVisible,
  }
}
