<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import {
  AI_MODEL_CAPABILITY_OPTIONS,
  AI_MODEL_PROVIDER_OPTIONS,
  AI_MODEL_RESOLUTION_OPTIONS,
  AI_MODEL_SIZE_OPTIONS,
  type AiModelCapability,
  type AiModelCreateInput,
  type AiModelResolution,
  type AiModelSize,
  type AiModelViewModel,
} from '@/entities/ai-model'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppNumberInput from '@/shared/ui/AppNumberInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{
  show: boolean
  model: AiModelViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AiModelCreateInput]
}>()

const initialValues: AiModelCreateInput = {
  displayName: '',
  modelCode: '',
  providerCode: 'toapis',
  enabled: true,
  isDefault: false,
  capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
  maxInputImages: 6,
  supportedSizes: ['1:1', '3:4', '4:3', '16:9'],
  supportedResolutions: ['1k', '2k', '4k'],
}

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<AiModelCreateInput>({ initialValues })
const [displayName] = defineField('displayName')
const [modelCode] = defineField('modelCode')
const [providerCode] = defineField('providerCode')
const [enabled] = defineField('enabled')
const [isDefault] = defineField('isDefault')
const [capabilities] = defineField('capabilities')
const [maxInputImages] = defineField('maxInputImages')
const [supportedSizes] = defineField('supportedSizes')
const [supportedResolutions] = defineField('supportedResolutions')
const editing = computed(() => props.model !== null)

watch(
  () => [props.show, props.model] as const,
  ([show, model]) => {
    if (!show) return
    resetForm({
      values: model
        ? {
            displayName: model.displayName,
            modelCode: model.modelCode,
            providerCode: model.providerCode,
            enabled: model.enabled,
            isDefault: model.isDefault,
            capabilities: [...model.capabilities],
            maxInputImages: model.maxInputImages,
            supportedSizes: [...model.supportedSizes],
            supportedResolutions: [...model.supportedResolutions],
          }
        : { ...initialValues },
    })
  },
)

function setCapabilities(values: AppOptionValue[]): void {
  capabilities.value = values as AiModelCapability[]
}

function setSizes(values: AppOptionValue[]): void {
  supportedSizes.value = values as AiModelSize[]
}

function setResolutions(values: AppOptionValue[]): void {
  supportedResolutions.value = values as AiModelResolution[]
}

const submit = handleSubmit((values) => {
  const parsed = z
    .object({
      displayName: z.string().trim().min(1, '请输入模型名称').max(100),
      modelCode: z.string().trim().min(1, '请输入模型 Code').max(100),
      providerCode: z.literal('toapis'),
      enabled: z.boolean(),
      isDefault: z.boolean(),
      capabilities: z
        .array(z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']))
        .min(1, '至少选择一项能力'),
      maxInputImages: z
        .number({ invalid_type_error: '请输入最大输入图片数' })
        .int('请输入整数')
        .min(0, '不能小于 0'),
      supportedSizes: z
        .array(z.enum(['1:1', '3:4', '4:3', '16:9']))
        .min(1, '至少选择一个尺寸'),
      supportedResolutions: z
        .array(z.enum(['1k', '2k', '4k']))
        .min(1, '至少选择一个 Resolution'),
    })
    .refine((value) => !value.isDefault || value.enabled, {
      path: ['enabled'],
      message: '默认模型必须启用',
    })
    .safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      displayName: fieldErrors.displayName?.[0],
      modelCode: fieldErrors.modelCode?.[0],
      providerCode: fieldErrors.providerCode?.[0],
      enabled: fieldErrors.enabled?.[0],
      capabilities: fieldErrors.capabilities?.[0],
      maxInputImages: fieldErrors.maxInputImages?.[0],
      supportedSizes: fieldErrors.supportedSizes?.[0],
      supportedResolutions: fieldErrors.supportedResolutions?.[0],
    })
    return
  }
  emit('save', parsed.data as AiModelCreateInput)
})
</script>

<template>
  <FormDialog
    :show="show"
    :title="editing ? '编辑模型' : '新增模型'"
    size="lg"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <div class="ai-model-form__grid">
        <NFormItem label="模型名称" :feedback="errors.displayName">
          <AppInput
            v-model="displayName"
            aria-label="模型名称"
            :maxlength="100"
          />
        </NFormItem>
        <NFormItem label="Model Code" :feedback="errors.modelCode">
          <AppInput
            v-model="modelCode"
            aria-label="Model Code"
            :maxlength="100"
            :disabled="editing"
          />
        </NFormItem>
        <NFormItem label="Provider" :feedback="errors.providerCode">
          <AppSelect
            v-model="providerCode"
            :options="[...AI_MODEL_PROVIDER_OPTIONS]"
            aria-label="Provider"
            :disabled="editing"
          />
        </NFormItem>
        <NFormItem label="最大输入图片数" :feedback="errors.maxInputImages">
          <AppNumberInput
            v-model="maxInputImages"
            aria-label="最大输入图片数"
            :min="0"
            :step="1"
          />
        </NFormItem>
        <NFormItem
          class="ai-model-form__wide"
          label="支持能力"
          :feedback="errors.capabilities"
        >
          <AppSelect
            :model-value="capabilities"
            :options="[...AI_MODEL_CAPABILITY_OPTIONS]"
            aria-label="支持能力"
            multiple
            :max-tag-count="'responsive'"
            @update:values="setCapabilities"
          />
        </NFormItem>
        <NFormItem
          class="ai-model-form__wide"
          label="支持尺寸"
          :feedback="errors.supportedSizes"
        >
          <AppSelect
            :model-value="supportedSizes"
            :options="[...AI_MODEL_SIZE_OPTIONS]"
            aria-label="支持尺寸"
            multiple
            :max-tag-count="'responsive'"
            @update:values="setSizes"
          />
        </NFormItem>
        <NFormItem
          class="ai-model-form__wide"
          label="支持 Resolution"
          :feedback="errors.supportedResolutions"
        >
          <AppSelect
            :model-value="supportedResolutions"
            :options="[...AI_MODEL_RESOLUTION_OPTIONS]"
            aria-label="支持 Resolution"
            multiple
            :max-tag-count="'responsive'"
            @update:values="setResolutions"
          />
        </NFormItem>
        <NFormItem label="启用模型" :feedback="errors.enabled">
          <AppSwitch v-model="enabled" :disabled="Boolean(model?.isDefault)" />
        </NFormItem>
        <NFormItem label="默认模型">
          <AppSwitch
            v-model="isDefault"
            :disabled="Boolean(model?.isDefault)"
          />
        </NFormItem>
      </div>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.ai-model-form__grid {
  display: grid;
  gap: 0 var(--space-4);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ai-model-form__wide {
  grid-column: 1 / -1;
}

@media (max-width: 720px) {
  .ai-model-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .ai-model-form__wide {
    grid-column: auto;
  }
}
</style>
