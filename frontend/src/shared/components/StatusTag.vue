<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'

export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'error'

const props = withDefaults(
  defineProps<{
    label: string
    tone?: StatusTone
  }>(),
  {
    tone: 'neutral',
  },
)

const tagType = computed(() =>
  props.tone === 'neutral' ? 'default' : props.tone,
)
</script>

<template>
  <NTag :type="tagType" size="small" :bordered="false">{{ label }}</NTag>
</template>
