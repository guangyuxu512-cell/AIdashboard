<script setup lang="ts">
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { computed, reactive, watch } from 'vue'

import {
  useAutomationApplicationConfigQuery,
  useUpsertAutomationApplicationConfigMutation,
  type AutomationInputFieldDto,
  type AutomationInputTypeDto,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import { AppButton, AppInput, AppNumberInput, AppSelect, AppSwitch } from '@/shared/ui'

interface FieldDraft {
  name: string
  label: string
  type: AutomationInputTypeDto
  required: boolean
  defaultValue: string | number | boolean | null
  optionsText: string
}

const props = defineProps<{
  show: boolean
  application: ProviderApplicationViewModel | null
}>()

const emit = defineEmits<{ 'update:show': [value: boolean] }>()
const message = useMessage()
const appId = computed(() => props.application?.appId ?? null)
const query = useAutomationApplicationConfigQuery(appId)
const mutation = useUpsertAutomationApplicationConfigMutation()
const form = reactive<{ fields: FieldDraft[] }>({ fields: [] })
const typeOptions = [
  { label: '文本', value: 'text' },
  { label: '数字', value: 'number' },
  { label: '开关', value: 'boolean' },
  { label: '选择', value: 'select' },
]

watch(
  [() => props.show, () => query.data.value],
  ([show, config]) => {
    if (!show) return
    form.fields = (config?.input_schema.fields ?? []).map((field) => ({
      name: field.name,
      label: field.label,
      type: field.type,
      required: field.required,
      defaultValue: (field.default_value ?? null) as FieldDraft['defaultValue'],
      optionsText: field.options.join(', '),
    }))
  },
  { immediate: true },
)

function addField(): void {
  form.fields.push({
    name: '',
    label: '',
    type: 'text',
    required: false,
    defaultValue: null,
    optionsText: '',
  })
}

function changeType(field: FieldDraft, value: unknown): void {
  field.type = value as AutomationInputTypeDto
  field.defaultValue = field.type === 'boolean' ? false : null
  if (field.type !== 'select') field.optionsText = ''
}

function parseOptions(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function toDto(field: FieldDraft): AutomationInputFieldDto {
  return {
    name: field.name.trim(),
    label: field.label.trim(),
    type: field.type,
    required: field.required,
    default_value: field.defaultValue,
    options: field.type === 'select' ? parseOptions(field.optionsText) : [],
  }
}

async function save(): Promise<void> {
  if (!props.application) return
  if (query.isPending.value) return
  if (query.error.value) {
    message.error(getErrorMessage(query.error.value))
    return
  }
  try {
    await mutation.mutateAsync({
      appId: props.application.appId,
      data: { input_schema: { fields: form.fields.map(toDto) } },
    })
    message.success('应用参数配置已保存')
    emit('update:show', false)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="`配置参数 · ${application?.appName ?? ''}`"
    size="lg"
    :submitting="mutation.isPending.value || query.isPending.value"
    @update:show="$emit('update:show', $event)"
    @submit="save"
  >
    <p class="parameter-config__description">
      参数定义由中控台手工维护；当前不推断影刀应用详情中的输入结构。
    </p>
    <p v-if="query.error.value" class="parameter-config__error">
      参数配置加载失败：{{ getErrorMessage(query.error.value) }}
    </p>
    <NForm label-placement="top">
      <div
        v-for="(field, index) in form.fields"
        :key="index"
        class="parameter-config__row"
      >
        <NFormItem label="参数名">
          <AppInput v-model="field.name" placeholder="例如 product_id" />
        </NFormItem>
        <NFormItem label="显示名称">
          <AppInput v-model="field.label" placeholder="例如 商品 ID" />
        </NFormItem>
        <NFormItem label="类型">
          <AppSelect
            :model-value="field.type"
            :options="typeOptions"
            @update:model-value="changeType(field, $event)"
          />
        </NFormItem>
        <NFormItem label="必填">
          <AppSwitch v-model="field.required" />
        </NFormItem>
        <NFormItem v-if="field.type === 'number'" label="默认值">
          <AppNumberInput
            :model-value="field.defaultValue as number"
            clearable
            @update:model-value="field.defaultValue = $event"
          />
        </NFormItem>
        <NFormItem v-else-if="field.type === 'boolean'" label="默认值">
          <AppSwitch
            :model-value="(field.defaultValue as boolean) ?? false"
            @update:model-value="field.defaultValue = $event"
          />
        </NFormItem>
        <NFormItem v-else-if="field.type === 'select'" label="默认值">
          <AppSelect
            :model-value="field.defaultValue as string"
            :options="parseOptions(field.optionsText).map((value) => ({ label: value, value }))"
            clearable
            @update:model-value="field.defaultValue = $event"
          />
        </NFormItem>
        <NFormItem v-else label="默认值">
          <AppInput
            :model-value="field.defaultValue as string"
            clearable
            @update:model-value="field.defaultValue = $event"
          />
        </NFormItem>
        <NFormItem v-if="field.type === 'select'" label="选项（逗号分隔）">
          <AppInput v-model="field.optionsText" placeholder="选项A, 选项B" />
        </NFormItem>
        <AppButton tone="danger" @click="form.fields.splice(index, 1)">
          删除参数
        </AppButton>
      </div>
    </NForm>
    <AppButton @click="addField">+ 添加参数</AppButton>
  </FormDialog>
</template>

<style scoped>
.parameter-config__description {
  margin-bottom: var(--space-4);
  color: var(--text-secondary);
}

.parameter-config__error {
  margin-bottom: var(--space-4);
  color: var(--color-error);
}

.parameter-config__row {
  display: grid;
  align-items: end;
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  gap: var(--space-3);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
</style>
