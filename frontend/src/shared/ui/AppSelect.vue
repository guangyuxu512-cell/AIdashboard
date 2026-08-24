<script setup lang="ts">
import { NSelect } from 'naive-ui'
import type { SelectFilter, SelectOption, SelectProps } from 'naive-ui'
import { computed } from 'vue'

import type { AppOptionValue, FieldWidth } from './types'

const props = withDefaults(
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
    filter?: SelectFilter
    menuProps?: SelectProps['menuProps']
    placement?: SelectProps['placement']
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
    renderLabel: undefined,
    filter: undefined,
    menuProps: undefined,
    placement: 'bottom-start',
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
    :filter="filter"
    :menu-props="mergedMenuProps"
    :placement="placement"
    @update:value="$emit('update:modelValue', $event)"
  />
</template>

<style>
.app-select-menu--viewport-safe {
  --n-height: var(--select-menu-max-height) !important;
}
</style>
