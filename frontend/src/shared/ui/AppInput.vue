<script setup lang="ts">
import { NInput } from 'naive-ui'

import type { FieldWidth } from './types'

withDefaults(
  defineProps<{
    modelValue?: string | null
    placeholder?: string
    width?: FieldWidth
    type?: 'text' | 'password' | 'textarea'
    clearable?: boolean
    disabled?: boolean
    loading?: boolean
    maxlength?: number
  }>(),
  {
    modelValue: null,
    placeholder: '',
    width: 'full',
    type: 'text',
    clearable: false,
    disabled: false,
    loading: false,
    maxlength: undefined,
  },
)

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <NInput
    class="app-field"
    :class="`app-field--${width}`"
    size="medium"
    :value="modelValue ?? ''"
    :type="type"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    :loading="loading"
    :maxlength="maxlength"
    @update:value="$emit('update:modelValue', $event)"
  />
</template>
