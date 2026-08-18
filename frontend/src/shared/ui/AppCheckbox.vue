<script setup lang="ts">
import { NCheckbox } from 'naive-ui'

withDefaults(
  defineProps<{
    modelValue?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: false,
    disabled: false,
  },
)

defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<template>
  <NCheckbox
    :checked="modelValue"
    :disabled="disabled"
    @update:checked="$emit('update:modelValue', $event)"
  >
    <slot />
  </NCheckbox>
</template>
