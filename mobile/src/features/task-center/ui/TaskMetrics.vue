<script setup lang="ts">
import { computed } from 'vue'

import { MobileSummaryStrip } from '@/shared/ui'

import type { TaskStatusFilter } from '../model/task-filter'

const props = defineProps<{
  filter: TaskStatusFilter
  totals: {
    running: number | null
    pending: number | null
    exception: number | null
    completed: number | null
  }
  busy: boolean
}>()

const emit = defineEmits<{
  select: [filter: Exclude<TaskStatusFilter, 'all'>]
}>()

const items = computed(() =>
  (
    [
      ['running', '运行中', props.totals.running, 'neutral'],
      ['pending', '待运行', props.totals.pending, 'neutral'],
      ['exception', '异常', props.totals.exception, 'danger'],
      ['completed', '已完成', props.totals.completed, 'neutral'],
    ] as const
  ).map(([key, label, value, tone]) => ({
    key,
    label,
    value: value ?? '—',
    tone,
    interactive: true,
    selected: props.filter === key,
    disabled: value === null,
    ariaLabel:
      props.filter === key
        ? `${label}，当前筛选，点击恢复全部任务`
        : `${label}，点击筛选`,
  })),
)

function selectMetric(key: string): void {
  if (
    key === 'running' ||
    key === 'pending' ||
    key === 'exception' ||
    key === 'completed'
  ) {
    emit('select', key)
  }
}
</script>

<template>
  <MobileSummaryStrip
    class="task-metrics"
    :items="items"
    :busy="busy"
    aria-label="任务总览"
    @select="selectMetric"
  />
</template>

<style scoped>
.task-metrics {
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
}

.task-metrics :deep(.mobile-summary-strip__surface) {
  backdrop-filter: blur(var(--visual-v2-metric-strip-blur));
}
</style>
