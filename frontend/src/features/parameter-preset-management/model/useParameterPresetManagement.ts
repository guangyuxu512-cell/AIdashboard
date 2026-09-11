import { computed, ref } from 'vue'

import {
  useAutomationParameterPresetManagementQuery,
  useYingdaoApplicationOptionsQuery,
  type AutomationParameterPresetDto,
} from '@/entities/automation-application'
import { getErrorMessage } from '@/shared/api'

export function useParameterPresetManagement() {
  const searchDraft = ref('')
  const selectedAppIdDraft = ref<string | null>(null)
  const filters = ref({ appId: null as string | null, query: null as string | null })
  const editorVisible = ref(false)
  const editorAppId = ref<string | null>(null)
  const editorPresetId = ref<string | null>(null)

  const applicationsQuery = useYingdaoApplicationOptionsQuery()
  const presetsQuery = useAutomationParameterPresetManagementQuery(filters)
  const applicationOptions = computed(() => applicationsQuery.data.value ?? [])
  const applicationNameById = computed(
    () => new Map(applicationOptions.value.map((item) => [item.app_id, item.app_name])),
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
    editorAppId.value = selectedAppIdDraft.value
    editorPresetId.value = null
    editorVisible.value = true
  }

  function openPreset(preset: AutomationParameterPresetDto): void {
    editorAppId.value = preset.app_id
    editorPresetId.value = preset.preset_id
    editorVisible.value = true
  }

  function closeEditor(): void {
    editorVisible.value = false
    editorPresetId.value = null
  }

  return {
    applicationNameById,
    applicationOptions,
    applicationsError: computed(() =>
      applicationsQuery.error.value ? getErrorMessage(applicationsQuery.error.value) : null,
    ),
    applicationsLoading: computed(() => applicationsQuery.isPending.value),
    closeEditor,
    editorAppId,
    editorPresetId,
    editorVisible,
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
