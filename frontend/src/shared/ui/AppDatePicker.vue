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
  }>(),
  {
    modelValue: null,
    type: 'date',
    width: 'full',
    clearable: true,
    disabled: false,
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
    @update:value="$emit('update:modelValue', $event)"
  />
</template>
