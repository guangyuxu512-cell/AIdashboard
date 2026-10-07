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
}>()
defineEmits<{ 'update:modelValue': [value: string | null] }>()
const options = computed(() => categoryOptions(props.nodes))
</script>

<template>
  <NCascader
    class="app-field app-field--full"
    :value="modelValue"
    :options="options"
    :disabled="disabled || loading"
    :placeholder="loading ? '正在读取类目' : '全部类目'"
    clearable
    filterable
    :show-path="true"
    size="medium"
    @update:value="
      $emit('update:modelValue', $event === null ? null : String($event))
    "
  />
</template>
