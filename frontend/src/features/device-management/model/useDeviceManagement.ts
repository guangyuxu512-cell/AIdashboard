import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'

import {
  deviceDataSource,
  type DeviceListFilters,
  type DeviceListItemViewModel,
  type DeviceSaveInput,
  useCreateDeviceMutation,
  useDeviceDetailQuery,
  useDeviceListQuery,
  useUpdateDeviceMutation,
} from '@/entities/device'
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
  const pageSize = ref(10)
  const detailDeviceId = ref<string | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<DeviceFormMode>('create')
  const formInitialValue = ref<DeviceFormViewModel | null>(null)
  const editingDeviceId = ref<string | null>(null)

  const listParams = computed(() => ({
    page: page.value,
    pageSize: pageSize.value,
    filters: appliedFilters.value,
  }))
  const listQuery = useDeviceListQuery(listParams)
  const detailQuery = useDeviceDetailQuery(detailDeviceId)
  const createMutation = useCreateDeviceMutation()
  const updateMutation = useUpdateDeviceMutation()

  const rows = computed(() => listQuery.data.value?.items ?? [])
  const total = computed(() => listQuery.data.value?.total ?? 0)
  const statistics = computed(() => ({
    total: total.value,
    enabled: rows.value.filter((device) => device.enabled).length,
    disabled: rows.value.filter((device) => !device.enabled).length,
  }))
  const listError = computed(() =>
    listQuery.error.value ? getErrorMessage(listQuery.error.value) : null,
  )
  const detailError = computed(() =>
    detailQuery.error.value ? getErrorMessage(detailQuery.error.value) : null,
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
    formVisible,
    formMode,
    formInitialValue,
    rows,
    total,
    statistics,
    filtersAvailable: deviceDataSource.supportsFilters,
    dataSourceDescription:
      deviceDataSource.mode === 'real'
        ? '数据来自 FastAPI；Worker、运行状态与资源数据尚未接入。'
        : '当前运行、资源与心跳信息来自 Frontend Fixture。',
    listLoading: listQuery.isPending,
    listError,
    detailDevice: computed(() => detailQuery.data.value ?? null),
    detailLoading: detailQuery.isPending,
    detailError,
    formSubmitting,
    query,
    resetFilters,
    setPageSize,
    retryList: listQuery.refetch,
    retryDetail: detailQuery.refetch,
    openDetail,
    openCreate,
    openEdit,
    saveDevice,
  }
}
