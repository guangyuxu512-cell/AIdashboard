import { useQuery } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { loadBusinessSkillCatalog } from './business-skill-data-source'

export const businessSkillQueryKeys = {
  catalog: (deviceId: string | null) =>
    ['business-skills', 'catalog', deviceId] as const,
}

export function useBusinessSkillCatalogQuery(
  deviceId: MaybeRefOrGetter<string | null>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() =>
      businessSkillQueryKeys.catalog(toValue(deviceId)),
    ),
    queryFn: () => loadBusinessSkillCatalog(toValue(deviceId)!),
    enabled: computed(
      () => Boolean(toValue(deviceId)) && Boolean(toValue(enabled)),
    ),
  })
}
