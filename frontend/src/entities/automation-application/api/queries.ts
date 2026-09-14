import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { automationApplicationApi } from './automation-application-api'
import type {
  AutomationApplicationConfigUpsertDto,
  AutomationParameterPresetListParams,
  AutomationParameterPresetDto,
  AutomationParameterPresetSaveDto,
  AutomationParameterPresetUpdateDto,
} from './contracts'

export const automationApplicationQueryKeys = {
  allPresets: ['automation-parameter-presets'] as const,
  presetManagementList: (params: AutomationParameterPresetListParams) =>
    [
      ...automationApplicationQueryKeys.allPresets,
      'list',
      params.deviceId ?? null,
      params.appId ?? null,
      params.query?.trim() || null,
      params.page ?? 1,
      params.pageSize ?? 20,
    ] as const,
  yingdaoApplicationsRoot: [
    'automation-app-configs',
    'yingdao',
    'applications',
  ] as const,
  yingdaoApplications: (deviceId: string | null) =>
    [
      ...automationApplicationQueryKeys.yingdaoApplicationsRoot,
      deviceId,
    ] as const,
  detail: (appId: string | null) =>
    ['automation-app-configs', 'yingdao', appId] as const,
  presets: (appId: string | null) =>
    ['automation-app-configs', 'yingdao', appId, 'parameter-presets'] as const,
}

function mergePreset(
  current: AutomationParameterPresetDto[] | undefined,
  preset: AutomationParameterPresetDto,
  { append }: { append: boolean },
): AutomationParameterPresetDto[] | undefined {
  if (!current) return append ? [preset] : current
  const index = current.findIndex((item) => item.preset_id === preset.preset_id)
  if (index < 0) return append ? [...current, preset] : current
  return current.map((item) =>
    item.preset_id === preset.preset_id ? preset : item,
  )
}

function updatePresetCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  preset: AutomationParameterPresetDto,
): void {
  // The mutation response is the latest source of truth for `version`.  Store
  // it before a background list refresh so a transient/refetch failure can
  // never make an open editor submit its prior expected_version again.
  queryClient.setQueryData<AutomationParameterPresetDto[]>(
    automationApplicationQueryKeys.presets(preset.app_id),
    (current) => mergePreset(current, preset, { append: true }),
  )
}

function refreshPresetLists(
  queryClient: ReturnType<typeof useQueryClient>,
  appId: string,
): void {
  // Refreshing list presentation is deliberately best-effort.  The mutation
  // has already succeeded and the editor has the returned DTO, so a list
  // request failure must not turn that success into an old draft/version.
  void queryClient
    .invalidateQueries({
      queryKey: automationApplicationQueryKeys.presets(appId),
      refetchType: 'active',
    })
    .catch(() => undefined)
  void queryClient
    .invalidateQueries({
      queryKey: automationApplicationQueryKeys.allPresets,
      refetchType: 'active',
    })
    .catch(() => undefined)
}

function removePresetFromCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  preset: Pick<AutomationParameterPresetDto, 'app_id' | 'preset_id'>,
): void {
  queryClient.setQueryData<AutomationParameterPresetDto[]>(
    automationApplicationQueryKeys.presets(preset.app_id),
    (current) => current?.filter((item) => item.preset_id !== preset.preset_id),
  )
}

export function useYingdaoApplicationOptionsQuery(
  deviceId: MaybeRefOrGetter<string | null> = null,
) {
  return useQuery({
    queryKey: computed(() =>
      automationApplicationQueryKeys.yingdaoApplications(toValue(deviceId)),
    ),
    queryFn: () =>
      automationApplicationApi.listYingdaoApplications(toValue(deviceId)),
  })
}

export function useAutomationParameterPresetManagementQuery(
  params: MaybeRefOrGetter<AutomationParameterPresetListParams>,
) {
  return useQuery({
    queryKey: computed(() =>
      automationApplicationQueryKeys.presetManagementList(toValue(params)),
    ),
    queryFn: () => automationApplicationApi.listAllPresets(toValue(params)),
  })
}

export function useAutomationParameterPresetsQuery(
  appId: MaybeRefOrGetter<string | null>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() =>
      automationApplicationQueryKeys.presets(toValue(appId)),
    ),
    queryFn: () => automationApplicationApi.listPresets(toValue(appId)!),
    enabled: computed(
      () => Boolean(toValue(appId)) && Boolean(toValue(enabled)),
    ),
  })
}

export function useSaveAutomationParameterPresetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      appId,
      presetId,
      data,
    }: {
      appId: string
      presetId: string | null
      data:
        AutomationParameterPresetSaveDto | AutomationParameterPresetUpdateDto
    }) =>
      presetId
        ? automationApplicationApi.updatePreset(
            appId,
            presetId,
            data as AutomationParameterPresetUpdateDto,
          )
        : automationApplicationApi.createPreset(appId, data),
    onSuccess: (preset, variables) => {
      updatePresetCaches(queryClient, preset)
      refreshPresetLists(queryClient, variables.appId)
    },
  })
}

export function useCopyAutomationParameterPresetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      appId,
      presetId,
      name,
    }: {
      appId: string
      presetId: string
      name: string
    }) => automationApplicationApi.copyPreset(appId, presetId, name),
    onSuccess: (preset, variables) => {
      updatePresetCaches(queryClient, preset)
      refreshPresetLists(queryClient, variables.appId)
    },
  })
}

export function useRemoveAutomationParameterPresetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      appId,
      presetId,
    }: {
      appId: string
      presetId: string
    }) => automationApplicationApi.removePreset(appId, presetId),
    onSuccess: (_, variables) => {
      removePresetFromCaches(queryClient, {
        app_id: variables.appId,
        preset_id: variables.presetId,
      })
      refreshPresetLists(queryClient, variables.appId)
    },
  })
}

export function useAutomationApplicationConfigQuery(
  appId: MaybeRefOrGetter<string | null>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() =>
      automationApplicationQueryKeys.detail(toValue(appId)),
    ),
    queryFn: () => automationApplicationApi.get(toValue(appId)!),
    enabled: computed(
      () => Boolean(toValue(appId)) && Boolean(toValue(enabled)),
    ),
  })
}

export function useUpsertAutomationApplicationConfigMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      appId,
      data,
    }: {
      appId: string
      data: AutomationApplicationConfigUpsertDto
    }) => automationApplicationApi.upsert(appId, data),
    onSuccess: (_, variables) =>
      queryClient.invalidateQueries({
        queryKey: automationApplicationQueryKeys.detail(variables.appId),
      }),
  })
}
