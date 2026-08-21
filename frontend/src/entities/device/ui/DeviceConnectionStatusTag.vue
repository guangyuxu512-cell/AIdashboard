<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import type { DeviceRuntimeStatus } from '../model/types'

const props = defineProps<{ status: DeviceRuntimeStatus }>()

const meta = computed(() => {
  switch (props.status) {
    case 'online':
    case 'busy':
      return { label: '在线', tone: 'success' as const }
    case 'error':
      return { label: '异常', tone: 'error' as const }
    case 'offline':
    case 'unavailable':
      return { label: '离线', tone: 'neutral' as const }
    default:
      return { label: '离线', tone: 'neutral' as const }
  }
})
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
