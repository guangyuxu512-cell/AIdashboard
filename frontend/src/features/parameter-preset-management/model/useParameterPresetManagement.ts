import { computed, ref } from 'vue'

import {
  useAutomationParameterPresetManagementQuery,
  useCopyAutomationParameterPresetMutation,
  useYingdaoApplicationOptionsQuery,
  type AutomationParameterPresetDto,
} from '@/entities/automation-application'
import { getErrorMessage } from '@/shared/api'

export function useParameterPresetManagement() {
  const searchDraft = ref('')
  const selectedAppIdDraft = ref<string | null>(null)
  const filters = ref({
    appId: null as string | null,
    query: null as string | null,
  })
  const editorVisible = ref(false)
  const editorAppId = ref<string | null>(null)
  const editorPresetId = ref<string | null>(null)
  const copyError = ref<string | null>(null)

  const applicationsQuery = useYingdaoApplicationOptionsQuery()
  const presetsQuery = useAutomationParameterPresetManagementQuery(filters)
  const copyPresetMutation = useCopyAutomationParameterPresetMutation()
  const applicationOptions = computed(() => applicationsQuery.data.value ?? [])
  const applicationNameById = computed(
    () =>
      new Map(
        applicationOptions.value.map((item) => [item.app_id, item.app_name]),
      ),
  )
  const rows = computed(() => presetsQuery.data.value ?? [])
  const listError = computed(() =>
    presetsQuery.error.value ? getErrorMessage(presetsQuery.error.value) : null,
  )

  function query(): void {
    filters.value = {
      appId: selectedAppIdDraft.value,
      query: searchDraft.value.trim() || null,
    }
  }

  function reset(): void {
    searchDraft.value = ''
    selectedAppIdDraft.value = null
    query()
  }

  function openCreate(): void {
    copyError.value = null
    editorAppId.value = selectedAppIdDraft.value
    editorPresetId.value = null
    editorVisible.value = true
  }

  function openPreset(preset: AutomationParameterPresetDto): void {
    copyError.value = null
    editorAppId.value = preset.app_id
    editorPresetId.value = preset.preset_id
    editorVisible.value = true
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

  return {
    applicationNameById,
    applicationOptions,
    applicationsError: computed(() =>
      applicationsQuery.error.value
        ? getErrorMessage(applicationsQuery.error.value)
        : null,
    ),
    applicationsLoading: computed(() => applicationsQuery.isPending.value),
    copyAndOpen,
    copyError,
    closeEditor,
    editorAppId,
    editorPresetId,
    editorVisible,
    handleSaved,
    listError,
    listLoading: computed(() => presetsQuery.isPending.value),
    openCreate,
    openPreset,
    query,
    reset,
    retryApplications: applicationsQuery.refetch,
    retryList: presetsQuery.refetch,
    rows,
    searchDraft,
    selectedAppIdDraft,
  }
}
