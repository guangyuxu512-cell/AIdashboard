<script setup lang="ts">
import { computed } from 'vue'

import { AppSelect } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

import { useShopSelectionOptionsQuery } from '../api/shop-queries'

const props = withDefaults(
  defineProps<{
    modelValue?: string | null
    disabled?: boolean
    clearable?: boolean
    placeholder?: string
  }>(),
  {
    modelValue: null,
    disabled: false,
    clearable: false,
    placeholder: '请选择店铺',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const query = useShopSelectionOptionsQuery()
const options = computed(() => query.data.value ?? [])

function update(value: AppOptionValue | null): void {
  emit('update:modelValue', value === null ? null : String(value))
}
</script>

<template>
  <AppSelect
    :model-value="props.modelValue"
    :options="options"
    :loading="query.isPending.value"
    :disabled="props.disabled"
    :clearable="props.clearable"
    :placeholder="props.placeholder"
    filterable
    @update:model-value="update"
  />
</template>
