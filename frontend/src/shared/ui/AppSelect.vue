<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { SelectOption, SelectProps } from 'naive-ui'

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
    renderLabel?: SelectProps['renderLabel']
  }>(),
  {
    modelValue: null,
    placeholder: '',
    width: 'full',
    clearable: false,
    filterable: false,
    loading: false,
    disabled: false,
    renderLabel: undefined,
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
    :render-label="renderLabel"
    @update:value="$emit('update:modelValue', $event)"
  />
</template>
