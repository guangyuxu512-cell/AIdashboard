import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { aiWorkbenchApi } from './ai-workbench-api'
import type {
  GenerationJobListQuery,
  ProductMaterialGroupListQuery,
  TemplateGroupListQuery,
} from './ai-workbench-api'
import type { GenerationJobPageDto, GenerationJobStatus } from './contracts'

export function generationJobPollingInterval(
  status: GenerationJobStatus | undefined,
): 1500 | false {
  return status === 'PENDING' || status === 'RUNNING' ? 1_500 : false
}

export function generationJobListPollingInterval(
  page: GenerationJobPageDto | undefined,
): 2000 | false {
  return page?.items.some(
    (job) => job.status === 'PENDING' || job.status === 'RUNNING',
  )
    ? 2_000
    : false
}

export const aiWorkbenchQueryKeys = {
  all: ['ai-workbench'] as const,
  models: ['ai-workbench', 'models'] as const,
  templates: ['ai-workbench', 'templates'] as const,
  templateGroups: (query: TemplateGroupListQuery) =>
    ['ai-workbench', 'templates', 'groups', query] as const,
  templateGroup: (id: string | null) =>
    ['ai-workbench', 'templates', 'group', id] as const,
  materials: ['ai-workbench', 'materials'] as const,
  materialGroups: (query: ProductMaterialGroupListQuery) =>
    ['ai-workbench', 'materials', 'groups', query] as const,
  materialGroup: (id: string | null) =>
    ['ai-workbench', 'materials', 'group', id] as const,
  generations: ['ai-workbench', 'generations'] as const,
  generationJobs: (query: GenerationJobListQuery) =>
    ['ai-workbench', 'generations', 'jobs', query] as const,
  generationJob: (id: string | null) =>
    ['ai-workbench', 'generations', 'job', id] as const,
}

export function useWorkbenchModelsQuery() {
  return useQuery({
    queryKey: aiWorkbenchQueryKeys.models,
    queryFn: () => aiWorkbenchApi.listModels(),
    staleTime: 30_000,
  })
}

export function useTemplateGroupsQuery(
  query: MaybeRefOrGetter<TemplateGroupListQuery>,
) {
  return useQuery({
    queryKey: computed(() =>
      aiWorkbenchQueryKeys.templateGroups(toValue(query)),
    ),
    queryFn: () => aiWorkbenchApi.listTemplateGroups(toValue(query)),
    placeholderData: keepPreviousData,
  })
}

export function useTemplateGroupQuery(id: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => aiWorkbenchQueryKeys.templateGroup(toValue(id))),
    queryFn: () => aiWorkbenchApi.getTemplateGroup(toValue(id)!),
    enabled: computed(() => Boolean(toValue(id))),
  })
}

export function useProductMaterialGroupsQuery(
  query: MaybeRefOrGetter<ProductMaterialGroupListQuery>,
) {
  return useQuery({
    queryKey: computed(() =>
      aiWorkbenchQueryKeys.materialGroups(toValue(query)),
    ),
    queryFn: () => aiWorkbenchApi.listProductMaterialGroups(toValue(query)),
    placeholderData: keepPreviousData,
  })
}

export function useProductMaterialGroupQuery(
  id: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() => aiWorkbenchQueryKeys.materialGroup(toValue(id))),
    queryFn: () => aiWorkbenchApi.getProductMaterialGroup(toValue(id)!),
    enabled: computed(() => Boolean(toValue(id))),
  })
}

export function useGenerationJobsQuery(
  query: MaybeRefOrGetter<GenerationJobListQuery>,
) {
  return useQuery({
    queryKey: computed(() =>
      aiWorkbenchQueryKeys.generationJobs(toValue(query)),
    ),
    queryFn: () => aiWorkbenchApi.listGenerationJobs(toValue(query)),
    placeholderData: keepPreviousData,
    refetchInterval: (result) =>
      generationJobListPollingInterval(result.state.data),
  })
}

export function useGenerationJobQuery(
  id: MaybeRefOrGetter<string | null>,
  options: { poll?: boolean } = {},
) {
  return useQuery({
    queryKey: computed(() => aiWorkbenchQueryKeys.generationJob(toValue(id))),
    queryFn: () => aiWorkbenchApi.getGenerationJob(toValue(id)!),
    enabled: computed(() => Boolean(toValue(id))),
    refetchInterval: options.poll
      ? (query) => {
          return generationJobPollingInterval(query.state.data?.status)
        }
      : false,
    refetchIntervalInBackground: options.poll === true,
    refetchOnWindowFocus: options.poll === true,
    refetchOnReconnect: options.poll === true,
  })
}

export function useInvalidateAiWorkbench() {
  const queryClient = useQueryClient()
  return {
    templates: () =>
      queryClient.invalidateQueries({
        queryKey: aiWorkbenchQueryKeys.templates,
      }),
    materials: () =>
      queryClient.invalidateQueries({
        queryKey: aiWorkbenchQueryKeys.materials,
      }),
    generations: () =>
      queryClient.invalidateQueries({
        queryKey: aiWorkbenchQueryKeys.generations,
      }),
  }
}
