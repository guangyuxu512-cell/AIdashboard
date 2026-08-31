<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import {
  GENERATION_MODE_META,
  type GenerationMode,
  type TemplateGroup,
  type TemplateGroupInput,
} from '../model/types'
import { AppDialog, AppInput, AppSelect } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'rename'
  group: TemplateGroup | null
  currentMode: GenerationMode
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: TemplateGroupInput]
}>()

const schema = z.object({
  name: z.string().trim().min(1, '请输入模板组名称').max(100),
  mode: z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<TemplateGroupInput>({
    initialValues: { name: '', mode: props.currentMode },
  })
const [name] = defineField('name')
const [generationMode] = defineField('mode')

const title = computed(() =>
  props.mode === 'create' ? '新建模板组' : '重命名模板组',
)

const generationModeOptions = Object.entries(GENERATION_MODE_META).map(
  ([value, meta]) => ({ value, label: meta.label }),
)

watch(
  () => [props.show, props.group, props.mode, props.currentMode] as const,
  ([show]) => {
    if (!show) return
    resetForm({
      values: {
        name: props.group?.name ?? '',
        mode: props.group?.mode ?? props.currentMode,
      },
    })
  },
)

function updateMode(value: AppOptionValue | null): void {
  if (value === 'NORMAL_GENERATION' || value === 'STYLE_REPLICATION') {
    generationMode.value = value
  }
}

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      name: fieldErrors.name?.[0],
      mode: fieldErrors.mode?.[0],
    })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <AppDialog
    :show="show"
    :title="title"
    size="sm"
    :positive-text="mode === 'create' ? '创建' : '保存'"
    @update:show="$emit('update:show', $event)"
    @confirm="submit"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem
        label="模板组名称"
        :validation-status="errors.name ? 'error' : undefined"
        :feedback="errors.name"
      >
        <AppInput
          v-model="name"
          placeholder="请输入模板组名称"
          :maxlength="100"
        />
      </NFormItem>
      <NFormItem
        v-if="mode === 'create'"
        label="生成模式"
        :validation-status="errors.mode ? 'error' : undefined"
        :feedback="errors.mode"
      >
        <AppSelect
          :model-value="generationMode"
          :options="generationModeOptions"
          aria-label="生成模式"
          @update:model-value="updateMode"
        />
      </NFormItem>
    </NForm>
  </AppDialog>
</template>
