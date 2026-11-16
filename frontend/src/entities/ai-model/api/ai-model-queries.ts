import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { aiWorkbenchQueryKeys } from '@/entities/ai-workbench'

import type { AiModelCreateInput, AiModelUpdateInput } from '../model/types'
import { aiModelDataSource } from './ai-model-data-source'

export const aiModelQueryKeys = {
  all: ['ai-models'] as const,
  list: ['ai-models', 'list'] as const,
}

export function useAiModelsQuery() {
  return useQuery({
    queryKey: aiModelQueryKeys.list,
    queryFn: () => aiModelDataSource.list(),
  })
}

function useAiModelMutation<Result, Variables>(
  action: (variables: Variables) => Promise<Result>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: action,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: aiModelQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: aiWorkbenchQueryKeys.models,
        }),
      ]),
  })
}

export function useCreateAiModelMutation() {
  return useAiModelMutation((input: AiModelCreateInput) =>
    aiModelDataSource.create(input),
  )
}

export function useUpdateAiModelMutation() {
  return useAiModelMutation(
    ({ modelId, input }: { modelId: string; input: AiModelUpdateInput }) =>
      aiModelDataSource.update(modelId, input),
  )
}

export function useSetDefaultAiModelMutation() {
  return useAiModelMutation((modelId: string) =>
    aiModelDataSource.setDefault(modelId),
  )
}
