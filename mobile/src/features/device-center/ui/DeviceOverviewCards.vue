<script setup lang="ts">
import { computed } from 'vue'

import { MobileSummaryStrip } from '@/shared/ui'

import type { DeviceOverview } from '../model/device-overview'
import type {
  DeviceMetricFilter,
  DeviceQuickFilter,
} from '../model/device-filter'

const props = withDefaults(
  defineProps<{
    overview: DeviceOverview
    filter?: DeviceQuickFilter
  }>(),
  { filter: 'all' },
)

const emit = defineEmits<{
  select: [filter: DeviceMetricFilter]
}>()

function selectMetric(key: string): void {
  if (key === 'online' || key === 'running' || key === 'offline') {
    emit('select', key)
  }
}

function metricAriaLabel(filter: DeviceMetricFilter, label: string): string {
  if (props.filter === filter) return `${label}，当前筛选，点击恢复全部`
  return `${label}，点击筛选`
}

const items = computed(() => [
  {
    key: 'online',
    label: '在线设备',
    value: props.overview.onlineCount ?? '—',
    icon: 'online' as const,
    tone: 'success' as const,
    interactive: true,
    selected: props.filter === 'online',
    disabled: props.overview.onlineCount === null,
    ariaLabel: metricAriaLabel('online', '在线设备'),
  },
  {
    key: 'running',
    label: '运行中',
    value: props.overview.runningCount ?? '—',
    icon: 'running' as const,
    tone: 'primary' as const,
    interactive: true,
    selected: props.filter === 'running',
    disabled: props.overview.runningCount === null,
    ariaLabel: metricAriaLabel('running', '运行中'),
  },
  {
    key: 'offline',
    label: '离线设备',
    value: props.overview.offlineCount ?? '—',
    icon: 'offline' as const,
    tone: 'muted' as const,
    interactive: true,
    selected: props.filter === 'offline',
    disabled: props.overview.offlineCount === null,
    ariaLabel: metricAriaLabel('offline', '离线设备'),
  },
])
</script>

<template>
  <MobileSummaryStrip
    :items="items"
    aria-label="设备总览"
    :busy="overview.dataState === 'loading'"
    @select="selectMetric"
  />
</template>
