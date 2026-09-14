import type { SelectOption } from 'naive-ui'
import { computed, ref } from 'vue'

import {
  useAutomationParameterPresetManagementQuery,
  useCopyAutomationParameterPresetMutation,
  useRemoveAutomationParameterPresetMutation,
  useYingdaoApplicationOptionsQuery,
  type AutomationParameterPresetDto,
} from '@/entities/automation-application'
import {
  type DeviceListFilters,
  useDeviceListQuery,
  useDeviceProviderInventoriesQuery,
} from '@/entities/device'
import { getErrorMessage, isInitialQueryLoading } from '@/shared/api'

function emptyDeviceFilters(): DeviceListFilters {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

export function useParameterPresetManagement() {
  const searchDraft = ref('')
  const selectedDeviceIdDraft = ref<string | null>(null)
  const selectedAppIdDraft = ref<string | null>(null)
  const filters = ref({
    deviceId: null as string | null,
    appId: null as string | null,
    query: null as string | null,
    page: 1,
    pageSize: 20,
  })
  const editorVisible = ref(false)
  const editorAppId = ref<string | null>(null)
  const editorPresetId = ref<string | null>(null)
  const copyError = ref<string | null>(null)
  const removeError = ref<string | null>(null)
  const removePreset = ref<AutomationParameterPresetDto | null>(null)
  const removeVisible = ref(false)

  const deviceQuery = useDeviceListQuery(
    computed(() => ({
      page: 1,
      pageSize: 100,
      filters: emptyDeviceFilters(),
    })),
  )
  const inventoryQuery = useDeviceProviderInventoriesQuery(selectedDeviceIdDraft)
  const applicationsQuery = useYingdaoApplicationOptionsQuery(selectedDeviceIdDraft)
  const presetsQuery = useAutomationParameterPresetManagementQuery(filters)
  const copyPresetMutation = useCopyAutomationParameterPresetMutation()
  const removePresetMutation = useRemoveAutomationParameterPresetMutation()
  const applicationOptions = computed(() => applicationsQuery.data.value ?? [])
  const deviceOptions = computed<SelectOption[]>(() =>
    (deviceQuery.data.value?.items ?? []).map((device) => ({
      label: device.deviceName,
      value: device.deviceId,
    })),
  )
  const applicationNameById = computed(
    () =>
      new Map(
        applicationOptions.value.map((item) => [item.app_id, item.app_name]),
      ),
  )
  const rows = computed(() => presetsQuery.data.value?.items ?? [])
  const page = computed(() => presetsQuery.data.value?.page ?? filters.value.page)
  const pageSize = computed(
    () => presetsQuery.data.value?.page_size ?? filters.value.pageSize,
  )
  const total = computed(() => presetsQuery.data.value?.total ?? 0)
  const invalidSelectedApp = computed(
    () =>
      selectedAppIdDraft.value !== null &&
      applicationsQuery.data.value !== undefined &&
      !applicationOptions.value.some(
        (application) => application.app_id === selectedAppIdDraft.value,
      ),
  )
  const listError = computed(() =>
    presetsQuery.error.value ? getErrorMessage(presetsQuery.error.value) : null,
  )
  const selectedDeviceCapabilityState = computed(() => {
    if (!selectedDeviceIdDraft.value) return null
    if (inventoryQuery.error.value) {
      return {
        kind: 'error' as const,
        message: getErrorMessage(inventoryQuery.error.value),
      }
    }
    if (inventoryQuery.isPending.value) {
      return { kind: 'loading' as const, message: '正在读取设备能力…' }
    }
    const inventory = inventoryQuery.data.value
    if (!inventory) {
      return {
        kind: 'unsynced' as const,
        message: '该设备尚未同步影刀应用能力，请先在设备能力中刷新。',
      }
    }
    if (inventory.providerStatus !== 'ready') {
      return {
        kind: 'unavailable' as const,
        message: inventory.statusReason || '该设备的影刀能力当前不可用。',
      }
    }
    return { kind: 'ready' as const, message: null }
  })

  function query(): void {
    filters.value = {
      deviceId: selectedDeviceIdDraft.value,
      appId: selectedAppIdDraft.value,
      query: searchDraft.value.trim() || null,
      page: 1,
      pageSize: filters.value.pageSize,
    }
  }

  function reset(): void {
    searchDraft.value = ''
    selectedDeviceIdDraft.value = null
    selectedAppIdDraft.value = null
    query()
  }

  function openCreate(): void {
    copyError.value = null
    editorAppId.value = invalidSelectedApp.value
      ? null
      : selectedAppIdDraft.value
    editorPresetId.value = null
    editorVisible.value = true
  }

  function openPreset(preset: AutomationParameterPresetDto): void {
    copyError.value = null
    editorAppId.value = preset.app_id
    editorPresetId.value = preset.preset_id
    editorVisible.value = true
  }

  function requestRemove(preset: AutomationParameterPresetDto): void {
    removeError.value = null
    removePreset.value = preset
    removeVisible.value = true
  }

  async function confirmRemove(): Promise<void> {
    const preset = removePreset.value
    if (!preset) return
    removeError.value = null
    const retreatToPreviousPage = rows.value.length === 1 && page.value > 1
    try {
      await removePresetMutation.mutateAsync({
        appId: preset.app_id,
        presetId: preset.preset_id,
      })
      if (editorPresetId.value === preset.preset_id) closeEditor()
      removeVisible.value = false
      removePreset.value = null
      if (retreatToPreviousPage) {
        filters.value = {
          ...filters.value,
          page: page.value - 1,
        }
      } else {
        await presetsQuery.refetch()
      }
    } catch (error) {
      removeError.value = getErrorMessage(error)
    }
  }

  function closeEditor(): void {
    editorVisible.value = false
    editorPresetId.value = null
  }

  function copyNameFor(preset: AutomationParameterPresetDto): string {
    const names = new Set(
      rows.value
        .filter((item) => item.app_id === preset.app_id)
        .map((item) => item.name),
    )
    let suffix = ' 副本'
    let sequence = 2
    const candidate = () =>
      `${preset.name.slice(0, Math.max(0, 100 - suffix.length))}${suffix}`
    while (names.has(candidate())) {
      suffix = ` 副本 ${sequence}`
      sequence += 1
    }
    return candidate()
  }

  async function copyAndOpen(
    preset: AutomationParameterPresetDto,
  ): Promise<void> {
    copyError.value = null
    try {
      const copied = await copyPresetMutation.mutateAsync({
        appId: preset.app_id,
        presetId: preset.preset_id,
        name: copyNameFor(preset),
      })
      editorAppId.value = copied.app_id
      editorPresetId.value = copied.preset_id
      editorVisible.value = true
    } catch (error) {
      copyError.value = getErrorMessage(error)
    }
  }

  function handleSaved(preset: AutomationParameterPresetDto): void {
    editorAppId.value = preset.app_id
    editorPresetId.value = preset.preset_id
  }

  function setPage(value: number): void {
    if (value === filters.value.page) return
    filters.value = { ...filters.value, page: value }
  }

  function setPageSize(value: number): void {
    if (value === filters.value.pageSize) return
    filters.value = { ...filters.value, page: 1, pageSize: value }
  }

  return {
    applicationNameById,
    applicationOptions,
    applicationsError: computed(() =>
      applicationsQuery.error.value
        ? getErrorMessage(applicationsQuery.error.value)
        : null,
    ),
    applicationsLoading: computed(() => applicationsQuery.isPending.value),
    applicationsLoaded: computed(() => applicationsQuery.isSuccess.value),
    deviceOptions,
    deviceOptionsError: computed(() =>
      deviceQuery.error.value ? getErrorMessage(deviceQuery.error.value) : null,
    ),
    deviceOptionsLoading: computed(() =>
      isInitialQueryLoading(deviceQuery.isPending.value, deviceQuery.data.value),
    ),
    copyAndOpen,
    copyError,
    confirmRemove,
    closeEditor,
    editorAppId,
    editorPresetId,
    editorVisible,
    handleSaved,
    invalidSelectedApp,
    listError,
    listLoading: computed(() => presetsQuery.isPending.value),
    openCreate,
    openPreset,
    page,
    pageSize,
    query,
    reset,
    removeError,
    removePreset,
    removeSubmitting: computed(() => removePresetMutation.isPending.value),
    removeVisible,
    retryApplications: applicationsQuery.refetch,
    retryList: presetsQuery.refetch,
    requestRemove,
    rows,
    searchDraft,
    selectedAppIdDraft,
    selectedDeviceCapabilityState,
    selectedDeviceIdDraft,
    setPage,
    setPageSize,
    total,
  }
}
