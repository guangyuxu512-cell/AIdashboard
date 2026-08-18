<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { SelectOption } from 'naive-ui'

import type { AppOptionValue, FieldWidth } from './types'

withDefaults(
  defineProps<{
    modelValue?: AppOptionValue | null
    options: SelectOption[]
    placeholder?: string
    width?: FieldWidth
    clearable?: boolean
    filterable?: boolean
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: null,
    placeholder: '',
    width: 'full',
    clearable: false,
    filterable: false,
    loading: false,
    disabled: false,
  },
)

defineEmits<{
  'update:modelValue': [value: AppOptionValue | null]
}>()
</script>

<template>
  <NSelect
    class="app-field"
    :class="`app-field--${width}`"
    size="medium"
    :value="modelValue"
    :options="options"
    :placeholder="placeholder"
    :clearable="clearable"
    :filterable="filterable"
    :loading="loading"
    :disabled="disabled"
    @update:value="$emit('update:modelValue', $event)"
  />
</template>
