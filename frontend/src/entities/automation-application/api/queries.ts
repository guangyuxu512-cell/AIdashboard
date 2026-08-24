import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { automationApplicationApi } from './automation-application-api'
import type { AutomationApplicationConfigUpsertDto } from './contracts'

export const automationApplicationQueryKeys = {
  detail: (appId: string | null) =>
    ['automation-app-configs', 'yingdao', appId] as const,
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
