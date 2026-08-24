<script setup lang="ts">
import { NFormItem } from 'naive-ui'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { AppInput, AppNumberInput, AppSelect, AppSwitch } from '@/shared/ui'

const props = defineProps<{
  schema: AutomationInputSchemaDto
  modelValue: Record<string, unknown>
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

function update(name: string, value: unknown): void {
  emit('update:modelValue', { ...props.modelValue, [name]: value })
}
</script>

<template>
  <NFormItem
    v-for="field in schema.fields"
    :key="field.name"
    :label="field.label"
    :required="field.required"
  >
    <AppNumberInput
      v-if="field.type === 'number'"
      :model-value="modelValue[field.name] as number"
      clearable
      :disabled="disabled"
      @update:model-value="update(field.name, $event)"
    />
    <AppSwitch
      v-else-if="field.type === 'boolean'"
      :model-value="(modelValue[field.name] as boolean) ?? false"
      :disabled="disabled"
      @update:model-value="update(field.name, $event)"
    />
    <AppSelect
      v-else-if="field.type === 'select'"
      :model-value="modelValue[field.name] as string"
      :options="field.options.map((value) => ({ label: value, value }))"
      clearable
      :disabled="disabled"
      @update:model-value="update(field.name, $event)"
    />
    <AppInput
      v-else
      :model-value="modelValue[field.name] as string"
      clearable
      :disabled="disabled"
      @update:model-value="update(field.name, $event)"
    />
  </NFormItem>
</template>
