import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'

import {
  useAiModelsQuery,
  useCreateAiModelMutation,
  useSetDefaultAiModelMutation,
  useUpdateAiModelMutation,
  type AiModelCreateInput,
  type AiModelUpdateInput,
  type AiModelViewModel,
} from '@/entities/ai-model'
import { getErrorMessage } from '@/shared/api'

export type AiModelStatusFilter = 'all' | 'enabled' | 'disabled'

function toUpdateInput(
  model: AiModelViewModel,
  overrides: Partial<AiModelUpdateInput> = {},
): AiModelUpdateInput {
  return {
    displayName: model.displayName,
    enabled: model.enabled,
    isDefault: model.isDefault,
    capabilities: [...model.capabilities],
    maxInputImages: model.maxInputImages,
    supportedSizes: [...model.supportedSizes],
    supportedResolutions: [...model.supportedResolutions],
    ...overrides,
  }
}

export function useAiModelManagement() {
  const message = useMessage()
  const statusFilter = ref<AiModelStatusFilter>('all')
  const selectedModel = ref<AiModelViewModel | null>(null)
  const formVisible = ref(false)
  const modelsQuery = useAiModelsQuery()
  const createMutation = useCreateAiModelMutation()
  const updateMutation = useUpdateAiModelMutation()
  const setDefaultMutation = useSetDefaultAiModelMutation()

  const models = computed(() => modelsQuery.data.value ?? [])
  const visibleModels = computed(() =>
    models.value.filter((model) => {
      if (statusFilter.value === 'enabled') return model.enabled
      if (statusFilter.value === 'disabled') return !model.enabled
      return true
    }),
  )
  const hasData = computed(() => modelsQuery.data.value !== undefined)
  const loading = computed(() => modelsQuery.isPending.value && !hasData.value)
  const error = computed(() =>
    modelsQuery.error.value && !hasData.value
      ? getErrorMessage(modelsQuery.error.value)
      : null,
  )
  const mutatingModelId = computed(() => {
    if (updateMutation.isPending.value)
      return updateMutation.variables.value?.modelId ?? null
    if (setDefaultMutation.isPending.value)
      return setDefaultMutation.variables.value ?? null
    return null
  })

  function openCreate(): void {
    selectedModel.value = null
    formVisible.value = true
  }

  function openEdit(model: AiModelViewModel): void {
    selectedModel.value = model
    formVisible.value = true
  }

  async function save(input: AiModelCreateInput): Promise<void> {
    try {
      if (selectedModel.value) {
        await updateMutation.mutateAsync({
          modelId: selectedModel.value.modelId,
          input: {
            displayName: input.displayName,
            enabled: input.enabled,
            isDefault: input.isDefault,
            capabilities: input.capabilities,
            maxInputImages: input.maxInputImages,
            supportedSizes: input.supportedSizes,
            supportedResolutions: input.supportedResolutions,
          },
        })
      } else {
        await createMutation.mutateAsync(input)
      }
      formVisible.value = false
      selectedModel.value = null
      message.success('模型已保存')
    } catch (saveError) {
      message.error(getErrorMessage(saveError))
    }
  }

  async function toggleEnabled(model: AiModelViewModel): Promise<void> {
    try {
      const updated = await updateMutation.mutateAsync({
        modelId: model.modelId,
        input: toUpdateInput(model, { enabled: !model.enabled }),
      })
      message.success(updated.enabled ? '模型已启用' : '模型已停用')
    } catch (toggleError) {
      message.error(getErrorMessage(toggleError))
    }
  }

  async function setDefault(model: AiModelViewModel): Promise<void> {
    try {
      await setDefaultMutation.mutateAsync(model.modelId)
      message.success('默认模型已更新')
    } catch (defaultError) {
      message.error(getErrorMessage(defaultError))
    }
  }

  return {
    statusFilter,
    selectedModel,
    formVisible,
    models,
    visibleModels,
    loading,
    error,
    formSubmitting: computed(
      () => createMutation.isPending.value || updateMutation.isPending.value,
    ),
    mutatingModelId,
    openCreate,
    openEdit,
    save,
    toggleEnabled,
    setDefault,
    retry: modelsQuery.refetch,
  }
}
