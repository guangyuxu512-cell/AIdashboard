<script setup lang="ts">
import { NCascader, type CascaderProps } from 'naive-ui'
import { computed } from 'vue'
import type { CategoryNode } from '../model/contracts'
import { categoryOptions } from '../model/selection-rules'

const props = defineProps<{
  modelValue: string | null
  nodes: CategoryNode[]
  disabled?: boolean
  loading?: boolean
  real?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()
const options = computed(() => categoryOptions(props.nodes, props.real))
function hasOption(
  nodes: ReturnType<typeof categoryOptions>,
  value: string,
): boolean {
  return nodes.some(
    (node) => node.value === value || hasOption(node.children ?? [], value),
  )
}
const value = computed(() =>
  props.real &&
  props.modelValue &&
  hasOption(options.value, `${props.modelValue}/*`)
    ? `${props.modelValue}/*`
    : props.modelValue,
)
function select(value: CascaderProps['value']) {
  if (Array.isArray(value)) return
  const selected = value == null ? null : String(value)
  // "全部" is a UI leaf, never a platform category. Persist/submit its
  // existing real parent path; the service still validates the actual tree.
  emit(
    'update:modelValue',
    props.real && selected?.endsWith('/*') && hasOption(options.value, selected)
      ? selected.slice(0, -2)
      : selected,
  )
}
const menuProps = {
  style: {
    maxWidth: 'calc(100vw - var(--space-3) * 2)',
    overflowX: 'auto',
    pointerEvents: 'auto',
  },
} as const
</script>

<template>
  <NCascader
    class="app-field app-field--full"
    :value="value"
    :options="options"
    check-strategy="child"
    placement="bottom-start"
    :menu-props="menuProps"
    :theme-overrides="{ menuHeight: 'var(--select-menu-max-height)' }"
    :disabled="disabled || loading"
    :placeholder="
      loading ? '正在读取类目' : real ? '请选择真实类目' : '全部类目'
    "
    clearable
    filterable
    :show-path="true"
    size="medium"
    @update:value="select"
  />
</template>
