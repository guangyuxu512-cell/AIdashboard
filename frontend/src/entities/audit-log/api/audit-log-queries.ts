import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import {
  auditLogDataSource,
  type AuditLogListParams,
} from './audit-log-data-source'

export const auditLogQueryKeys = {
  all: ['audit-logs'] as const,
  list: (params: AuditLogListParams) => ['audit-logs', params] as const,
}

export function useAuditLogsQuery(
  params: MaybeRefOrGetter<AuditLogListParams>,
) {
  return useQuery({
    queryKey: computed(() => auditLogQueryKeys.list(toValue(params))),
    queryFn: () => auditLogDataSource.list(toValue(params)),
    placeholderData: keepPreviousData,
  })
}
