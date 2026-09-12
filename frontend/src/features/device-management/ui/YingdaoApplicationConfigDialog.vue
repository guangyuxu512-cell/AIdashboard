<script setup lang="ts">
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { computed, nextTick, reactive, ref, watch } from 'vue'

import {
  useAutomationApplicationConfigQuery,
  useUpsertAutomationApplicationConfigMutation,
  type AutomationInputFieldDto,
  type AutomationInputSchemaDto,
  type AutomationInputTypeDto,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import { getErrorMessage, toApiError } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import {
  AppButton,
  AppInput,
  AppNumberInput,
  AppSelect,
  AppSwitch,
} from '@/shared/ui'

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
  /** Edit a preset-local schema without writing the shared app template. */
  presetSchema?: AutomationInputSchemaDto | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirmPresetSchema: [schema: AutomationInputSchemaDto]
}>()
const message = useMessage()
const appId = computed(() => props.application?.appId ?? null)
const isPresetSchemaEditor = computed(() => props.presetSchema !== undefined)
const query = useAutomationApplicationConfigQuery(
  appId,
  () => !isPresetSchemaEditor.value,
)
const mutation = useUpsertAutomationApplicationConfigMutation()
const sourceSchema = computed(() =>
  isPresetSchemaEditor.value
    ? props.presetSchema ?? { fields: [] }
    : (query.data.value?.input_schema ?? { fields: [] }),
)
const form = reactive<{ fields: FieldDraft[] }>({ fields: [] })
const parameterList = ref<HTMLElement | null>(null)
const fieldErrors = ref<Record<string, string>>({})
const initializedKey = ref('')
const typeOptions = [
  { label: '文本', value: 'text' },
  { label: '数字', value: 'number' },
  { label: '开关', value: 'boolean' },
  { label: '选择', value: 'select' },
]

watch(
  [() => props.show, appId, sourceSchema],
  ([show, currentAppId, schema]) => {
    if (!show) {
      initializedKey.value = ''
      fieldErrors.value = {}
      return
    }
    if (!isPresetSchemaEditor.value && query.data.value === undefined) return
    const key = `${currentAppId ?? ''}:${JSON.stringify(schema)}`
    if (key === initializedKey.value) return
    initializedKey.value = key
    fieldErrors.value = {}
    form.fields = schema.fields.map((field) => ({
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

async function addField(): Promise<void> {
  form.fields.push({
    name: '',
    label: '',
    type: 'text',
    required: false,
    defaultValue: null,
    optionsText: '',
  })
  await nextTick()
  parameterList.value?.lastElementChild?.scrollIntoView({
    block: 'nearest',
    behavior: 'smooth',
  })
}

function changeType(field: FieldDraft, value: unknown): void {
  field.type = value as AutomationInputTypeDto
  field.defaultValue = field.type === 'boolean' ? false : null
  if (field.type !== 'select') field.optionsText = ''
}

function effectiveLabel(field: FieldDraft): string {
  return field.label.trim() || field.name.trim() || '该参数'
}

function errorKey(index: number, field: string): string {
  return `${index}.${field}`
}

function clearFieldError(index: number, field: string): void {
  delete fieldErrors.value[errorKey(index, field)]
  delete fieldErrors.value[errorKey(index, 'row')]
}

function validateDrafts(): Record<string, string> {
  const errors: Record<string, string> = {}
  const normalizedNames = form.fields.map((field) => field.name.trim())
  const duplicateNames = new Set(
    normalizedNames.filter(
      (name, index) => Boolean(name) && normalizedNames.indexOf(name) !== index,
    ),
  )
  const namePattern = /^[\p{L}\p{N}_.-]+$/u

  form.fields.forEach((field, index) => {
    const name = normalizedNames[index]!
    const label = effectiveLabel(field)
    if (!name) {
      errors[errorKey(index, 'name')] = '请输入参数名'
    } else if (!namePattern.test(name)) {
      errors[errorKey(index, 'name')] =
        '参数名只能包含 Unicode 字母、数字、下划线、点和连字符'
    } else if (duplicateNames.has(name)) {
      errors[errorKey(index, 'name')] = '参数名不能重复'
    }

    const options = parseOptions(field.optionsText)
    if (field.type === 'select') {
      if (!options.length || new Set(options).size !== options.length) {
        errors[errorKey(index, 'options')] = `${label}必须提供不重复的选项`
      }
    } else if (options.length) {
      errors[errorKey(index, 'options')] = `${label}不是选择参数，不能提供选项`
    }

    if (field.defaultValue === null) return
    const validDefault =
      (field.type === 'text' && typeof field.defaultValue === 'string') ||
      (field.type === 'number' &&
        typeof field.defaultValue === 'number' &&
        Number.isFinite(field.defaultValue)) ||
      (field.type === 'boolean' && typeof field.defaultValue === 'boolean') ||
      (field.type === 'select' &&
        typeof field.defaultValue === 'string' &&
        options.includes(field.defaultValue))
    if (!validDefault) {
      errors[errorKey(index, 'defaultValue')] =
        `${label}的默认值不符合${field.type}类型`
    }
  })
  return errors
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

function applyServerFieldErrors(error: unknown): boolean {
  const apiError = toApiError(error)
  if (
    apiError.code !== 'VALIDATION_ERROR' ||
    !Array.isArray(apiError.details)
  ) {
    return false
  }
  const errors: Record<string, string> = {}
  for (const detail of apiError.details) {
    if (typeof detail !== 'object' || detail === null) continue
    const record = detail as { loc?: unknown; msg?: unknown }
    const location = Array.isArray(record.loc) ? record.loc : []
    const fieldsIndex = location.findIndex((part) => part === 'fields')
    const index = location[fieldsIndex + 1]
    if (typeof index !== 'number' || !form.fields[index]) continue
    const leaf = location.at(-1)
    const field =
      leaf === 'name' ||
      leaf === 'label' ||
      leaf === 'type' ||
      leaf === 'options' ||
      leaf === 'default_value'
        ? leaf === 'default_value'
          ? 'defaultValue'
          : leaf
        : 'row'
    errors[errorKey(index, field)] =
      typeof record.msg === 'string' ? record.msg : '参数配置校验失败'
  }
  if (!Object.keys(errors).length) return false
  fieldErrors.value = errors
  return true
}

async function save(): Promise<void> {
  if (!props.application) return
  if (!isPresetSchemaEditor.value && query.isPending.value) return
  if (!isPresetSchemaEditor.value && query.error.value) {
    message.error(getErrorMessage(query.error.value))
    return
  }
  fieldErrors.value = validateDrafts()
  if (Object.keys(fieldErrors.value).length) return
  const inputSchema = { fields: form.fields.map(toDto) }
  if (isPresetSchemaEditor.value) {
    emit('confirmPresetSchema', inputSchema)
    emit('update:show', false)
    return
  }
  try {
    await mutation.mutateAsync({
      appId: props.application.appId,
      data: { input_schema: inputSchema },
    })
    message.success('应用参数配置已保存')
    emit('update:show', false)
  } catch (error) {
    if (!applyServerFieldErrors(error)) message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="`${isPresetSchemaEditor ? '管理预设字段' : '配置参数'} · ${application?.appName ?? ''}`"
    size="lg"
    :submitting="mutation.isPending.value || (!isPresetSchemaEditor && query.isPending.value)"
    @update:show="$emit('update:show', $event)"
    @submit="save"
  >
    <template #description>
      <template v-if="isPresetSchemaEditor">
        字段只属于当前参数预设；不会修改应用共用字段模板或其他预设。
      </template>
      <template v-else>
        参数定义由中控台手工维护；当前不推断影刀应用详情中的输入结构。
      </template>
    </template>
    <p v-if="!isPresetSchemaEditor && query.error.value" class="parameter-config__error">
      参数配置加载失败：{{ getErrorMessage(query.error.value) }}
    </p>
    <NForm label-placement="top">
      <div ref="parameterList" class="parameter-config__list">
        <div
          v-for="(field, index) in form.fields"
          :key="index"
          class="parameter-config__row"
          data-testid="parameter-config-field"
        >
          <NFormItem
            label="参数名"
            :validation-status="
              fieldErrors[errorKey(index, 'name')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'name')]"
          >
            <AppInput
              v-model="field.name"
              placeholder="例如 商品列表"
              :maxlength="100"
              @update:model-value="clearFieldError(index, 'name')"
            />
          </NFormItem>
          <NFormItem
            label="显示名称（留空使用参数名）"
            :validation-status="
              fieldErrors[errorKey(index, 'label')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'label')]"
          >
            <AppInput
              v-model="field.label"
              placeholder="例如 商品 ID"
              :maxlength="100"
              @update:model-value="clearFieldError(index, 'label')"
            />
          </NFormItem>
          <NFormItem
            label="类型"
            :validation-status="
              fieldErrors[errorKey(index, 'type')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'type')]"
          >
            <AppSelect
              :model-value="field.type"
              :options="typeOptions"
              @update:model-value="changeType(field, $event)"
            />
          </NFormItem>
          <NFormItem label="必填">
            <AppSwitch v-model="field.required" />
          </NFormItem>
          <NFormItem
            v-if="field.type === 'number'"
            label="默认值"
            :validation-status="
              fieldErrors[errorKey(index, 'defaultValue')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'defaultValue')]"
          >
            <AppNumberInput
              :model-value="field.defaultValue as number"
              clearable
              @update:model-value="field.defaultValue = $event"
            />
          </NFormItem>
          <NFormItem
            v-else-if="field.type === 'boolean'"
            label="默认值"
            :validation-status="
              fieldErrors[errorKey(index, 'defaultValue')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'defaultValue')]"
          >
            <AppSwitch
              :model-value="(field.defaultValue as boolean) ?? false"
              @update:model-value="field.defaultValue = $event"
            />
          </NFormItem>
          <NFormItem
            v-else-if="field.type === 'select'"
            label="默认值"
            :validation-status="
              fieldErrors[errorKey(index, 'defaultValue')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'defaultValue')]"
          >
            <AppSelect
              :model-value="field.defaultValue as string"
              :options="
                parseOptions(field.optionsText).map((value) => ({
                  label: value,
                  value,
                }))
              "
              clearable
              @update:model-value="field.defaultValue = $event"
            />
          </NFormItem>
          <NFormItem
            v-else
            label="默认值"
            :validation-status="
              fieldErrors[errorKey(index, 'defaultValue')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'defaultValue')]"
          >
            <AppInput
              :model-value="field.defaultValue as string"
              clearable
              @update:model-value="field.defaultValue = $event"
            />
          </NFormItem>
          <NFormItem
            v-if="field.type === 'select'"
            label="选项（逗号分隔）"
            :validation-status="
              fieldErrors[errorKey(index, 'options')] ? 'error' : undefined
            "
            :feedback="fieldErrors[errorKey(index, 'options')]"
          >
            <AppInput
              v-model="field.optionsText"
              placeholder="选项A, 选项B"
              @update:model-value="clearFieldError(index, 'options')"
            />
          </NFormItem>
          <p
            v-if="fieldErrors[errorKey(index, 'row')]"
            class="parameter-config__row-error"
          >
            {{ fieldErrors[errorKey(index, 'row')] }}
          </p>
          <AppButton
            class="parameter-config__remove"
            tone="danger"
            @click="form.fields.splice(index, 1)"
          >
            删除参数
          </AppButton>
        </div>
      </div>
    </NForm>
    <template #footer-start>
      <AppButton @click="addField">+ 添加参数</AppButton>
    </template>
  </FormDialog>
</template>

<style scoped>
.parameter-config__error {
  margin-bottom: var(--space-3);
  color: var(--color-error);
}

.parameter-config__row {
  display: grid;
  align-items: end;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  gap: var(--space-2) var(--space-3);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.parameter-config__row + .parameter-config__row {
  margin-top: var(--space-3);
}

.parameter-config__remove {
  justify-self: start;
}

.parameter-config__row-error {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-error);
  font-size: var(--font-size-secondary);
}
</style>
