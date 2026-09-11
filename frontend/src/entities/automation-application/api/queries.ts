import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { automationApplicationApi } from './automation-application-api'
import type {
  AutomationApplicationConfigUpsertDto,
  AutomationParameterPresetSaveDto,
} from './contracts'

export const automationApplicationQueryKeys = {
  detail: (appId: string | null) =>
    ['automation-app-configs', 'yingdao', appId] as const,
  presets: (appId: string | null) =>
    ['automation-app-configs', 'yingdao', appId, 'parameter-presets'] as const,
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
      data: AutomationParameterPresetSaveDto
    }) =>
      presetId
        ? automationApplicationApi.updatePreset(appId, presetId, data)
        : automationApplicationApi.createPreset(appId, data),
    onSuccess: (_, variables) =>
      queryClient.invalidateQueries({
        queryKey: automationApplicationQueryKeys.presets(variables.appId),
      }),
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
    onSuccess: (_, variables) =>
      queryClient.invalidateQueries({
        queryKey: automationApplicationQueryKeys.presets(variables.appId),
      }),
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
