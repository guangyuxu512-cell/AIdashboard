<script setup lang="ts">
import { computed } from 'vue'

import { MobileSummaryStrip } from '@/shared/ui'

import type { DeviceOverview } from '../model/device-overview'

const props = defineProps<{ overview: DeviceOverview }>()

const items = computed(() => [
  {
    key: 'online',
    label: '在线设备',
    value: props.overview.onlineCount ?? '—',
    icon: 'desktop-o',
    tone: 'success' as const,
  },
  {
    key: 'running',
    label: '运行中',
    value: props.overview.runningCount ?? '—',
    icon: 'play-circle-o',
    tone: 'primary' as const,
  },
  {
    key: 'offline',
    label: '离线设备',
    value: props.overview.offlineCount ?? '—',
    icon: 'close',
    tone: 'muted' as const,
  },
])
</script>

<template>
  <MobileSummaryStrip
    :items="items"
    aria-label="设备总览"
    :busy="overview.dataState === 'loading'"
  />
</template>
