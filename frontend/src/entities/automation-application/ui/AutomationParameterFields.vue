<script setup lang="ts">
import { computed } from 'vue'

import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { mapAutomationParameterFields } from '../model/parameters'

const props = defineProps<{
  schema: AutomationInputSchemaDto
  modelValue: Record<string, unknown>
  disabled?: boolean
  preserveEmptyString?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

const fields = computed(() => mapAutomationParameterFields(props.schema))
</script>

<template>
  <SchemaParameterFields
    :fields="fields"
    :model-value="modelValue"
    :disabled="disabled"
    :preserve-empty-string="preserveEmptyString"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>
