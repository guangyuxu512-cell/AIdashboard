<script setup lang="ts">
import { NDatePicker } from 'naive-ui'

export type AppDateValue = number | [number, number] | null

withDefaults(
  defineProps<{
    modelValue?: AppDateValue
    type?: 'date' | 'daterange'
    clearable?: boolean
    disabled?: boolean
    placeholder?: string
    startPlaceholder?: string
    endPlaceholder?: string
  }>(),
  {
    modelValue: null,
    type: 'date',
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
    class="app-date-picker"
    :class="{ 'app-date-picker--range': type === 'daterange' }"
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

<style scoped>
.app-date-picker {
  width: var(--date-picker-width-single);
  flex: 0 0 auto;
}

.app-date-picker--range {
  width: var(--date-picker-width-range);
}
</style>
