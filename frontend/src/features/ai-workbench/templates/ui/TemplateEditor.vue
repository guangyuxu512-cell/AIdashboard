<script setup lang="ts">
import { watch } from 'vue'
import { X } from '@lucide/vue'
import { NDynamicTags, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import {
  TEMPLATE_OUTPUT_FORMAT_META,
  TEMPLATE_SIZE_OPTIONS,
  type PromptTemplate,
  type PromptTemplateInput,
  type TemplateOutputFormat,
  type TemplateSize,
} from '../model/types'
import {
  AppButton,
  AppInput,
  AppNumberInput,
  AppSelect,
  AppSwitch,
} from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{
  template: PromptTemplate
}>()

const emit = defineEmits<{
  close: []
  save: [input: PromptTemplateInput]
}>()

const schema = z.object({
  name: z.string().trim().min(1, '请输入模板名称').max(100),
  enabled: z.boolean(),
  outputFormat: z.enum(['SINGLE', 'COLLAGE_2X2']),
  size: z.enum(TEMPLATE_SIZE_OPTIONS),
  count: z.number().int().min(1, '数量不能小于 1').max(8),
  variables: z.array(z.string().trim().min(1)).max(20),
  prompt: z.string().trim().min(1, '请输入 Prompt').max(5000),
  negativePrompt: z.string().max(2000),
})

function valuesFromTemplate(template: PromptTemplate): PromptTemplateInput {
  return {
    name: template.name,
    enabled: template.enabled,
    outputFormat: template.outputFormat,
    size: template.size,
    count: template.count,
    variables: [...template.variables],
    prompt: template.prompt,
    negativePrompt: template.negativePrompt,
  }
}

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<PromptTemplateInput>({
    initialValues: valuesFromTemplate(props.template),
  })

const [name] = defineField('name')
const [enabled] = defineField('enabled')
const [outputFormat] = defineField('outputFormat')
const [size] = defineField('size')
const [count] = defineField('count')
const [variables] = defineField('variables')
const [prompt] = defineField('prompt')
const [negativePrompt] = defineField('negativePrompt')

const outputFormatOptions = Object.entries(TEMPLATE_OUTPUT_FORMAT_META).map(
  ([value, meta]) => ({ value, label: meta.label }),
)
const sizeOptions = TEMPLATE_SIZE_OPTIONS.map((value) => ({
  value,
  label: value,
}))

watch(
  () => props.template.id,
  () => resetForm({ values: valuesFromTemplate(props.template) }),
)

function updateOutputFormat(value: AppOptionValue | null): void {
  if (value === 'SINGLE' || value === 'COLLAGE_2X2') {
    outputFormat.value = value as TemplateOutputFormat
  }
}

function updateSize(value: AppOptionValue | null): void {
  if (TEMPLATE_SIZE_OPTIONS.includes(value as TemplateSize)) {
    size.value = value as TemplateSize
  }
}

function updateCount(value: number | null): void {
  if (value !== null) count.value = value
}

function updateVariables(value: string[]): void {
  variables.value = value
}

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      name: fieldErrors.name?.[0],
      count: fieldErrors.count?.[0],
      variables: fieldErrors.variables?.[0],
      prompt: fieldErrors.prompt?.[0],
      negativePrompt: fieldErrors.negativePrompt?.[0],
    })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <section class="template-editor" aria-label="模板编辑">
    <header class="template-editor__header">
      <strong>模板编辑</strong>
      <AppButton tone="text" aria-label="关闭模板编辑" @click="$emit('close')">
        <X :size="16" />
      </AppButton>
    </header>

    <NForm
      class="template-editor__form"
      label-placement="top"
      @submit.prevent="submit"
    >
      <NFormItem
        label="模板名称"
        :validation-status="errors.name ? 'error' : undefined"
        :feedback="errors.name"
      >
        <AppInput v-model="name" :maxlength="100" aria-label="模板名称" />
      </NFormItem>

      <label class="template-editor__switch-row">
        <span>启用</span>
        <AppSwitch v-model="enabled" aria-label="模板启用" />
      </label>

      <div class="template-editor__field-grid">
        <NFormItem label="输出格式">
          <AppSelect
            :model-value="outputFormat"
            :options="outputFormatOptions"
            aria-label="输出格式"
            @update:model-value="updateOutputFormat"
          />
        </NFormItem>
        <NFormItem label="比例">
          <AppSelect
            :model-value="size"
            :options="sizeOptions"
            aria-label="比例"
            @update:model-value="updateSize"
          />
        </NFormItem>
        <NFormItem
          label="数量"
          :validation-status="errors.count ? 'error' : undefined"
          :feedback="errors.count"
        >
          <AppNumberInput
            :model-value="count"
            :min="1"
            :max="8"
            aria-label="数量"
            @update:model-value="updateCount"
          />
        </NFormItem>
      </div>

      <NFormItem
        label="变量"
        :validation-status="errors.variables ? 'error' : undefined"
        :feedback="errors.variables"
      >
        <NDynamicTags
          :value="variables"
          size="medium"
          aria-label="变量"
          @update:value="updateVariables"
        />
      </NFormItem>

      <NFormItem
        label="Prompt"
        :validation-status="errors.prompt ? 'error' : undefined"
        :feedback="errors.prompt"
      >
        <AppInput
          v-model="prompt"
          class="template-editor__textarea template-editor__textarea--prompt"
          type="textarea"
          :maxlength="5000"
          aria-label="Prompt"
        />
      </NFormItem>

      <NFormItem
        label="Negative Prompt"
        :validation-status="errors.negativePrompt ? 'error' : undefined"
        :feedback="errors.negativePrompt"
      >
        <AppInput
          v-model="negativePrompt"
          class="template-editor__textarea"
          type="textarea"
          :maxlength="2000"
          aria-label="Negative Prompt"
        />
      </NFormItem>

      <footer class="template-editor__footer">
        <AppButton tone="primary" @click="submit">保存</AppButton>
      </footer>
    </NForm>
  </section>
</template>

<style scoped>
.template-editor {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 100%;
  flex-direction: column;
}

.template-editor__header {
  position: sticky;
  z-index: 1;
  top: 0;
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
}

.template-editor__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.template-editor__form {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  padding: var(--space-4);
}

.template-editor__switch-row {
  display: flex;
  min-height: var(--control-height-large);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: 0 var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  background: var(--bg-subtle);
}

.template-editor__field-grid {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 var(--space-2);
}

.template-editor__textarea {
  min-height: calc(var(--control-height-large) * 2);
}

.template-editor__textarea--prompt {
  min-height: calc(var(--control-height-large) * 4);
}

.template-editor__footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  margin: auto calc(var(--space-4) * -1) calc(var(--space-4) * -1);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
}

@media (max-width: 1200px) {
  .template-editor__field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
