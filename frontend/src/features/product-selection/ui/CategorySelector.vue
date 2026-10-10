<script setup lang="ts">
import { NCascader } from 'naive-ui'
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
defineEmits<{ 'update:modelValue': [value: string | null] }>()
const options = computed(() => categoryOptions(props.nodes, !props.real))
</script>

<template>
  <NCascader
    class="app-field app-field--full"
    :value="modelValue"
    :options="options"
    :check-strategy="real ? 'all' : 'child'"
    :disabled="disabled || loading"
    :placeholder="
      loading ? '正在读取类目' : real ? '请选择真实类目' : '全部类目'
    "
    clearable
    filterable
    :show-path="true"
    size="medium"
    @update:value="
      $emit('update:modelValue', $event === null ? null : String($event))
    "
  />
</template>
