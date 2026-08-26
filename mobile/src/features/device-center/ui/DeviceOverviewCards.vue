<script setup lang="ts">
import { computed } from 'vue'

import type { DeviceOverview } from '../model/device-overview'

const props = defineProps<{ overview: DeviceOverview }>()

const loadedText = computed(() => {
  if (props.overview.dataState === 'loading') return '设备列表加载中'
  if (props.overview.dataState === 'error') return '设备统计不可用'
  return `当前已加载 ${props.overview.loadedCount} 台设备`
})

const connectionHint = computed(() => {
  if (props.overview.dataState === 'loading') return '连接统计等待设备数据'
  if (props.overview.dataState === 'error') {
    return '设备加载失败，连接统计不可用'
  }
  if (props.overview.unreportedCount) {
    return `${props.overview.unreportedCount} 台连接状态未上报`
  }
  return '连接状态均已上报'
})

const connectionCardHint = computed(() => {
  if (props.overview.dataState === 'loading') return '等待设备数据'
  if (props.overview.dataState === 'error') return '统计不可用'
  return '当前已加载'
})

const activeTaskHint = computed(() => {
  if (props.overview.dataState === 'loading') {
    return '当前任务统计中'
  }
  if (props.overview.dataState === 'error') {
    return '设备加载失败，任务统计不可用'
  }
  if (props.overview.activeState === 'loading') return '当前任务统计中'
  if (props.overview.activeState === 'error') return '当前任务统计失败'

  const confirmed = `已确认 ${props.overview.activeConfirmedCount}/${props.overview.loadedCount} 台`
  if (props.overview.activeUnknownCount > 0) {
    return props.overview.activeBackgroundErrorCount > 0
      ? `${confirmed}，部分刷新失败`
      : confirmed
  }
  if (props.overview.activeBackgroundErrorCount > 0) {
    return '部分状态刷新失败'
  }
  return confirmed
})
</script>

<template>
  <section class="device-overview" aria-labelledby="device-overview-title">
    <div class="device-overview__scope">
      <strong id="device-overview-title">{{ loadedText }}</strong>
      <span>{{ connectionHint }}</span>
    </div>

    <dl class="device-overview__cards" aria-live="polite">
      <div class="device-overview__card device-overview__card--online">
        <dt>在线设备</dt>
        <dd data-testid="overview-online">
          {{ overview.onlineCount ?? '—' }}
        </dd>
        <small>{{ connectionCardHint }}</small>
      </div>
      <div class="device-overview__card device-overview__card--running">
        <dt>运行中任务</dt>
        <dd data-testid="overview-running">
          {{ overview.runningCount ?? '—' }}
        </dd>
        <small data-testid="overview-running-hint">{{ activeTaskHint }}</small>
      </div>
      <div class="device-overview__card device-overview__card--offline">
        <dt>离线设备</dt>
        <dd data-testid="overview-offline">
          {{ overview.offlineCount ?? '—' }}
        </dd>
        <small>{{ connectionCardHint }}</small>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.device-overview {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) 0
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.device-overview__scope {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: baseline;
  justify-content: space-between;
}

.device-overview__scope strong {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.device-overview__scope span,
.device-overview__card small {
  min-width: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  overflow-wrap: anywhere;
}

.device-overview__cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  min-width: 0;
  margin: 0;
  overflow: hidden;
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-default);
  border-radius: var(--radius-card);
}

.device-overview__card {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  align-content: center;
}

.device-overview__card + .device-overview__card {
  border-left: var(--border-width) solid var(--border-subtle);
}

.device-overview__card dt,
.device-overview__card dd {
  min-width: 0;
  margin: 0;
}

.device-overview__card dt {
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-body);
}

.device-overview__card dd {
  order: -1;
  font-size: var(--font-size-display);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-display);
}

.device-overview__card--online dd {
  color: var(--status-success);
}

.device-overview__card--running dd {
  color: var(--status-info);
}

.device-overview__card--offline dd {
  color: var(--text-secondary);
}
</style>
