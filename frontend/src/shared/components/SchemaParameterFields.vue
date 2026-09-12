<script setup lang="ts">
import { NFormItem } from 'naive-ui'

import type {
  SchemaParameterField,
  SchemaParameterFieldsLayout,
  SchemaParameterScalar,
} from '@/shared/types/schema-parameter'
import {
  AppButton,
  AppInput,
  AppNumberInput,
  AppSelect,
  AppSwitch,
} from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'
import {
  decodeSchemaOption,
  encodeSchemaOption,
} from '@/shared/utils/schema-parameters'

const props = withDefaults(
  defineProps<{
    fields: SchemaParameterField[]
    modelValue: Record<string, unknown>
    disabled?: boolean
    preserveEmptyString?: boolean
    layout?: SchemaParameterFieldsLayout
    referenceValues?: Record<string, unknown>
    showRestore?: boolean
    showRemove?: boolean
  }>(),
  {
    layout: 'stacked',
    referenceValues: () => ({}),
    showRestore: false,
    showRemove: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
  restore: [name: string]
  remove: [name: string]
}>()

function update(name: string, value: unknown): void {
  const next = { ...props.modelValue }
  if (
    value === null ||
    value === undefined ||
    (value === '' && !props.preserveEmptyString)
  ) {
    delete next[name]
  }
  else next[name] = value
  emit('update:modelValue', next)
}

function optionValue(value: unknown): AppOptionValue | null {
  return encodeSchemaOption(value)
}

function optionLabel(value: SchemaParameterScalar): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

function displayValue(value: unknown): string {
  if (value === '') return '（空）'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
</script>

<template>
  <NFormItem
    v-for="field in fields"
    :key="field.name"
    :label="field.label"
    :required="field.required"
    :label-placement="layout === 'stacked' ? undefined : 'left'"
    :class="[
      'schema-parameter-fields__item',
      `schema-parameter-fields__item--${layout}`,
    ]"
  >
    <div
      :class="[
        'schema-parameter-field',
        {
          'schema-parameter-field--comparison': layout === 'comparison',
          'schema-parameter-field--compact': layout === 'compact',
        },
      ]"
    >
      <span
        v-if="layout === 'comparison'"
        class="schema-parameter-field__reference"
      >
        {{ displayValue(referenceValues[field.name]) }}
      </span>
      <div class="schema-parameter-field__control">
        <AppNumberInput
          v-if="field.control === 'integer' || field.control === 'number'"
          :model-value="modelValue[field.name] as number"
          clearable
          :disabled="disabled"
          :min="field.min"
          :max="field.max"
          :step="field.step ?? (field.control === 'integer' ? 1 : undefined)"
          @update:model-value="update(field.name, $event)"
        />
        <AppSwitch
          v-else-if="field.control === 'boolean'"
          :model-value="(modelValue[field.name] as boolean) ?? false"
          :disabled="disabled"
          @update:model-value="update(field.name, $event)"
        />
        <AppSelect
          v-else-if="field.control === 'select'"
          :model-value="optionValue(modelValue[field.name])"
          :options="
            (field.options ?? []).map((value) => ({
              label: optionLabel(value),
              value: optionValue(value)!,
            }))
          "
          clearable
          :disabled="disabled"
          @update:model-value="update(field.name, decodeSchemaOption($event))"
        />
        <AppInput
          v-else
          :model-value="modelValue[field.name] as string"
          clearable
          :disabled="disabled"
          @update:model-value="update(field.name, $event)"
        />
        <small v-if="field.description">{{ field.description }}</small>
      </div>
      <AppButton
        v-if="layout === 'comparison' && showRestore"
        tone="text"
        @click="$emit('restore', field.name)"
      >
        恢复
      </AppButton>
      <AppButton
        v-if="layout === 'compact' && showRemove && !field.required"
        tone="text"
        @click="$emit('remove', field.name)"
      >
        移除
      </AppButton>
    </div>
  </NFormItem>
</template>

<style scoped>
.schema-parameter-field {
  display: flex;
  min-width: 0;
  width: 100%;
  flex-direction: column;
  gap: var(--space-1);
}

.schema-parameter-fields__item--compact,
.schema-parameter-fields__item--comparison {
  margin-bottom: var(--space-2);
}

.schema-parameter-fields__item--compact :deep(.n-form-item-label),
.schema-parameter-fields__item--comparison :deep(.n-form-item-label) {
  flex: 0 0 var(--field-width-sm);
  width: var(--field-width-sm);
  padding-right: var(--space-3);
}

.schema-parameter-field--comparison {
  display: grid;
  align-items: center;
  gap: var(--space-2);
  grid-template-columns: minmax(0, 0.75fr) minmax(0, 1fr) auto;
}

.schema-parameter-field--compact {
  flex-direction: row;
  align-items: center;
}

.schema-parameter-field--compact .schema-parameter-field__control {
  flex: 1;
}

.schema-parameter-field__reference {
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schema-parameter-field__control {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.schema-parameter-field small {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  line-height: var(--line-height-body);
}

@media (max-width: 640px) {
  .schema-parameter-fields__item--compact :deep(.n-form-item-label),
  .schema-parameter-fields__item--comparison :deep(.n-form-item-label) {
    flex-basis: var(--field-width-xs);
    width: var(--field-width-xs);
  }

  .schema-parameter-field--comparison {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  }
}
</style>
