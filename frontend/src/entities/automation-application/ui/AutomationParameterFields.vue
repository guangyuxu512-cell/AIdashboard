<script setup lang="ts">
import { computed } from 'vue'

import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import type { SchemaParameterFieldsLayout } from '@/shared/types/schema-parameter'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { mapAutomationParameterFields } from '../model/parameters'

const props = defineProps<{
  schema: AutomationInputSchemaDto
  modelValue: Record<string, unknown>
  disabled?: boolean
  preserveEmptyString?: boolean
  layout?: SchemaParameterFieldsLayout
  referenceValues?: Record<string, unknown>
  showRestore?: boolean
  showRemove?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
  restore: [name: string]
  remove: [name: string]
}>()

const fields = computed(() => mapAutomationParameterFields(props.schema))
</script>

<template>
  <SchemaParameterFields
    :fields="fields"
    :model-value="modelValue"
    :disabled="disabled"
    :preserve-empty-string="preserveEmptyString"
    :layout="layout"
    :reference-values="referenceValues"
    :show-restore="showRestore"
    :show-remove="showRemove"
    @update:model-value="emit('update:modelValue', $event)"
    @restore="emit('restore', $event)"
    @remove="emit('remove', $event)"
  />
</template>
