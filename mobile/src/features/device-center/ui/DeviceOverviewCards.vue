<script setup lang="ts">
import type { DeviceOverview } from '../model/device-overview'

defineProps<{ overview: DeviceOverview }>()
</script>

<template>
  <section class="device-overview" aria-label="设备总览">
    <dl
      class="device-overview__cards"
      aria-live="polite"
      :aria-busy="overview.dataState === 'loading'"
    >
      <div class="device-overview__card device-overview__card--online">
        <dd data-testid="overview-online">
          {{ overview.onlineCount ?? '—' }}
        </dd>
        <dt>在线设备</dt>
      </div>
      <div class="device-overview__card device-overview__card--running">
        <dd data-testid="overview-running">
          {{ overview.runningCount ?? '—' }}
        </dd>
        <dt>运行中</dt>
      </div>
      <div class="device-overview__card device-overview__card--offline">
        <dd data-testid="overview-offline">
          {{ overview.offlineCount ?? '—' }}
        </dd>
        <dt>离线设备</dt>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.device-overview {
  display: grid;
  min-width: 0;
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) 0
    max(var(--layout-page-padding-x), var(--safe-area-left));
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
