<script setup lang="ts">
import { NDatePicker } from 'naive-ui'

import type { FieldWidth } from './types'

export type AppDateValue = number | [number, number] | null

withDefaults(
  defineProps<{
    modelValue?: AppDateValue
    type?: 'date' | 'daterange'
    width?: FieldWidth
    clearable?: boolean
    disabled?: boolean
    placeholder?: string
    startPlaceholder?: string
    endPlaceholder?: string
  }>(),
  {
    modelValue: null,
    type: 'date',
    width: 'full',
    clearable: true,
    disabled: false,
    placeholder: undefined,
    startPlaceholder: undefined,
    endPlaceholder: undefined,
  },
)

defineEmits<{
  'update:modelValue': [value: AppDateValue]
}>()
</script>

<template>
  <NDatePicker
    class="app-field"
    :class="`app-field--${width}`"
    size="medium"
    :value="modelValue"
    :type="type"
    :clearable="clearable"
    :disabled="disabled"
    :placeholder="placeholder"
    :start-placeholder="startPlaceholder"
    :end-placeholder="endPlaceholder"
    @update:value="$emit('update:modelValue', $event)"
  />
</template>
