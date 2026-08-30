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
  if (
    key === 'all' ||
    key === 'online' ||
    key === 'running' ||
    key === 'offline'
  ) {
    emit('select', key)
  }
}

function metricAriaLabel(filter: DeviceQuickFilter, label: string): string {
  if (filter === 'all') return `${label}，显示全部设备`
  if (props.filter === filter) return `${label}，当前筛选，点击恢复全部`
  return `${label}，点击筛选`
}

const items = computed(() => [
  {
    key: 'all',
    label: '全部设备',
    value: props.overview.totalCount ?? '—',
    interactive: true,
    selected: props.filter === 'all',
    disabled: props.overview.totalCount === null,
    ariaLabel: metricAriaLabel('all', '全部设备'),
  },
  {
    key: 'online',
    label: '在线设备',
    value: props.overview.onlineCount ?? '—',
    interactive: true,
    selected: props.filter === 'online',
    disabled: props.overview.onlineCount === null,
    ariaLabel: metricAriaLabel('online', '在线设备'),
  },
  {
    key: 'running',
    label: '运行中',
    value: props.overview.runningCount ?? '—',
    interactive: true,
    selected: props.filter === 'running',
    disabled: props.overview.runningCount === null,
    ariaLabel: metricAriaLabel('running', '运行中'),
  },
  {
    key: 'offline',
    label: '离线设备',
    value: props.overview.offlineCount ?? '—',
    interactive: true,
    selected: props.filter === 'offline',
    disabled: props.overview.offlineCount === null,
    ariaLabel: metricAriaLabel('offline', '离线设备'),
  },
])
</script>

<template>
  <div class="device-overview-cards">
    <MobileSummaryStrip
      :items="items"
      aria-label="设备总览"
      :busy="overview.dataState === 'loading'"
      @select="selectMetric"
    />
  </div>
</template>

<style scoped>
.device-overview-cards {
  --summary-strip-height: var(--device-list-summary-height);
  --summary-strip-padding-x: 0px;
  --summary-strip-padding-y: 0px;
  --summary-strip-safe-area-right: 0px;
  --summary-strip-safe-area-left: 0px;
  --summary-strip-radius: var(--device-list-summary-radius);
  --summary-strip-background: var(--device-list-summary-background);
  --summary-strip-border-color: var(--device-list-summary-border);
  --summary-strip-shadow: var(--device-list-summary-shadow);
  --summary-strip-divider: var(--device-list-summary-divider);
  --summary-strip-divider-inset: var(--device-list-summary-divider-inset);
  --summary-strip-metric-gap: var(--device-list-summary-metric-gap);
  --summary-strip-metric-padding-top: var(
    --device-list-summary-metric-padding-top
  );
  --summary-strip-metric-padding-x: var(--device-list-summary-metric-padding-x);
  --summary-strip-metric-padding-bottom: var(
    --device-list-summary-metric-padding-bottom
  );
  --summary-strip-value-size: var(--device-list-summary-value-size);
  --summary-strip-value-weight: var(--device-list-summary-value-weight);
  --summary-strip-value-line-height: var(
    --device-list-summary-value-line-height
  );
  --summary-strip-value-letter-spacing: var(
    --device-list-summary-value-letter-spacing
  );
  --summary-strip-label-size: var(--device-list-summary-label-size);
  --summary-strip-label-weight: var(--device-list-summary-label-weight);
  --summary-strip-label-line-height: var(
    --device-list-summary-label-line-height
  );
  --summary-strip-label-color: var(--device-list-summary-label-color);
  --summary-strip-selected-bottom: var(--device-list-summary-selected-bottom);
  --summary-strip-selected-width: var(--device-list-summary-selected-width);
  --summary-strip-selected-height: var(--device-list-summary-selected-height);
  --summary-strip-selected-color: var(--device-list-summary-selected-color);
  --summary-strip-selected-value-color: var(
    --device-list-summary-selected-value-color
  );
  --summary-strip-selected-value-weight: var(
    --device-list-summary-selected-value-weight
  );
  --summary-strip-selected-label-color: var(
    --device-list-summary-selected-label-color
  );
  --summary-strip-selected-label-weight: var(
    --device-list-summary-selected-label-weight
  );
  width: 100%;
  min-width: 0;
}
</style>
