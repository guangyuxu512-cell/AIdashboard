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
  --summary-strip-height: var(--visual-v2-metric-strip-height);
  --summary-strip-padding-x: 0px;
  --summary-strip-padding-y: 0px;
  --summary-strip-safe-area-right: 0px;
  --summary-strip-safe-area-left: 0px;
  --summary-strip-radius: var(--visual-v2-metric-strip-radius);
  --summary-strip-background: var(--visual-v2-metric-strip-background);
  --summary-strip-border-color: var(--visual-v2-metric-strip-border-color);
  --summary-strip-shadow: var(--visual-v2-metric-strip-shadow);
  --summary-strip-divider: var(--visual-v2-metric-strip-divider);
  --summary-strip-divider-inset: var(--visual-v2-metric-strip-divider-inset);
  --summary-strip-metric-gap: var(--visual-v2-metric-gap);
  --summary-strip-metric-padding-top: var(--visual-v2-metric-padding-top);
  --summary-strip-metric-padding-x: var(--visual-v2-metric-padding-x);
  --summary-strip-metric-padding-bottom: var(--visual-v2-metric-padding-bottom);
  --summary-strip-value-size: var(--typography-v2-metric-number-size);
  --summary-strip-value-weight: var(--typography-v2-metric-number-weight);
  --summary-strip-value-line-height: var(
    --typography-v2-metric-number-line-height
  );
  --summary-strip-value-letter-spacing: var(
    --typography-v2-metric-number-letter-spacing
  );
  --summary-strip-label-size: var(--typography-v2-metric-label-size);
  --summary-strip-label-weight: var(--typography-v2-metric-label-weight);
  --summary-strip-label-line-height: var(
    --typography-v2-metric-label-line-height
  );
  --summary-strip-label-color: var(--visual-v2-metric-label-color);
  --summary-strip-selected-bottom: var(--visual-v2-metric-selected-bottom);
  --summary-strip-selected-width: var(--visual-v2-metric-selected-width);
  --summary-strip-selected-height: var(--visual-v2-metric-selected-height);
  --summary-strip-selected-color: var(--visual-v2-metric-selected-color);
  --summary-strip-selected-value-color: var(
    --visual-v2-metric-selected-value-color
  );
  --summary-strip-selected-value-weight: var(
    --visual-v2-metric-selected-value-weight
  );
  --summary-strip-selected-label-color: var(
    --visual-v2-metric-selected-label-color
  );
  --summary-strip-selected-label-weight: var(
    --visual-v2-metric-selected-label-weight
  );
  width: 100%;
  min-width: 0;
}

.device-overview-cards :deep(.mobile-summary-strip__surface) {
  backdrop-filter: blur(var(--visual-v2-metric-strip-blur));
}
</style>
