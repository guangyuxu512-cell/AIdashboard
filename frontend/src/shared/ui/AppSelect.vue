<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { SelectFilter, SelectOption, SelectProps } from 'naive-ui'
import { computed } from 'vue'

import type { AppOptionValue, AppSelectValue, FieldWidth } from './types'

const props = withDefaults(
  defineProps<{
    modelValue?: AppSelectValue | null
    options: SelectOption[]
    placeholder?: string
    width?: FieldWidth
    clearable?: boolean
    filterable?: boolean
    loading?: boolean
    disabled?: boolean
    multiple?: boolean
    maxTagCount?: number | 'responsive'
    renderLabel?: SelectProps['renderLabel']
    filter?: SelectFilter
    menuProps?: SelectProps['menuProps']
    placement?: SelectProps['placement']
    to?: SelectProps['to']
    viewportSafeMenu?: boolean
  }>(),
  {
    modelValue: null,
    placeholder: '',
    width: 'full',
    clearable: false,
    filterable: false,
    loading: false,
    disabled: false,
    multiple: false,
    maxTagCount: undefined,
    renderLabel: undefined,
    filter: undefined,
    menuProps: undefined,
    placement: 'bottom-start',
    to: undefined,
    viewportSafeMenu: true,
  },
)

const mergedMenuProps = computed<SelectProps['menuProps']>(() => ({
  ...props.menuProps,
  class: [
    props.viewportSafeMenu ? 'app-select-menu--viewport-safe' : null,
    props.menuProps?.class,
  ],
}))

const emit = defineEmits<{
  'update:modelValue': [value: AppOptionValue | null]
  'update:values': [value: AppOptionValue[]]
}>()

function updateValue(value: AppSelectValue | null): void {
  if (props.multiple) {
    emit('update:values', Array.isArray(value) ? value : [])
    return
  }
  if (!Array.isArray(value)) emit('update:modelValue', value)
}
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
    :multiple="multiple"
    :max-tag-count="maxTagCount"
    :render-label="renderLabel"
    :filter="filter"
    :menu-props="mergedMenuProps"
    :placement="placement"
    :to="to"
    @update:value="updateValue"
  />
</template>

<style>
.app-select-menu--viewport-safe {
  --n-height: var(--select-menu-max-height) !important;
  pointer-events: auto;
}
</style>
