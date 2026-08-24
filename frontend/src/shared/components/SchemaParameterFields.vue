<script setup lang="ts">
import { NFormItem } from 'naive-ui'

import type {
  SchemaParameterField,
  SchemaParameterScalar,
} from '@/shared/types/schema-parameter'
import { AppInput, AppNumberInput, AppSelect, AppSwitch } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'
import {
  decodeSchemaOption,
  encodeSchemaOption,
} from '@/shared/utils/schema-parameters'

const props = defineProps<{
  fields: SchemaParameterField[]
  modelValue: Record<string, unknown>
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

function update(name: string, value: unknown): void {
  const next = { ...props.modelValue }
  if (value === null || value === undefined || value === '') delete next[name]
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
</script>

<template>
  <NFormItem
    v-for="field in fields"
    :key="field.name"
    :label="field.label"
    :required="field.required"
  >
    <div class="schema-parameter-field">
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

.schema-parameter-field small {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  line-height: var(--line-height-body);
}
</style>
