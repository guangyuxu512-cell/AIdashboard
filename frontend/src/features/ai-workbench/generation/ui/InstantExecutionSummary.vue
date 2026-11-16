<script setup lang="ts">
import { Download } from '@lucide/vue'
import { NProgress } from 'naive-ui'
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  GENERATION_EXECUTION_STATUS_META,
  type InstantExecutionView,
} from '../model/types'

const props = defineProps<{
  execution: InstantExecutionView | null
}>()

defineEmits<{
  downloadAll: []
}>()

const progressPercentage = computed(() => {
  const total = props.execution?.totalCount ?? 0
  return total === 0
    ? 0
    : ((props.execution?.completedCount ?? 0) / total) * 100
})

const progressLabel = computed(() => `${progressPercentage.value.toFixed(1)}%`)
</script>

<template>
  <header
    class="instant-execution-summary"
    data-testid="instant-execution-summary"
    :data-execution-status="execution?.status ?? 'EMPTY'"
  >
    <div class="instant-execution-summary__heading">
      <h2>执行结果</h2>
      <div v-if="execution" class="instant-execution-summary__state">
        <StatusTag
          :label="GENERATION_EXECUTION_STATUS_META[execution.status].label"
          :tone="GENERATION_EXECUTION_STATUS_META[execution.status].tone"
        />
        <strong
          >{{ execution.completedCount }} / {{ execution.totalCount }}</strong
        >
        <span>{{ progressLabel }}</span>
      </div>
    </div>

    <template v-if="execution">
      <NProgress
        data-testid="instant-execution-progress"
        type="line"
        :percentage="progressPercentage"
        :show-indicator="false"
        :processing="execution.status === 'RUNNING'"
      />
      <div class="instant-execution-summary__lower">
        <dl
          class="instant-execution-summary__stats"
          data-testid="instant-execution-stats"
        >
          <div>
            <dt>成功</dt>
            <dd>{{ execution.successCount }}</dd>
          </div>
          <div>
            <dt>生成中</dt>
            <dd>{{ execution.runningCount }}</dd>
          </div>
          <div>
            <dt>等待中</dt>
            <dd>{{ execution.waitingCount }}</dd>
          </div>
          <div>
            <dt>失败</dt>
            <dd>{{ execution.failedCount }}</dd>
          </div>
        </dl>
        <AppButton
          tone="text"
          :disabled="execution.successCount === 0"
          @click="$emit('downloadAll')"
        >
          <Download :size="15" />
          下载全部
        </AppButton>
      </div>
    </template>
  </header>
</template>

<style scoped>
.instant-execution-summary {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  flex-direction: column;
  gap: var(--space-2);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.instant-execution-summary__heading,
.instant-execution-summary__state,
.instant-execution-summary__lower,
.instant-execution-summary__stats,
.instant-execution-summary__stats > div {
  display: flex;
  min-width: 0;
  align-items: center;
}

.instant-execution-summary__heading,
.instant-execution-summary__lower {
  justify-content: space-between;
  gap: var(--space-3);
}

.instant-execution-summary h2 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.instant-execution-summary__state {
  gap: var(--space-2);
}

.instant-execution-summary__state strong,
.instant-execution-summary__state span,
.instant-execution-summary__stats dd {
  font-variant-numeric: tabular-nums;
}

.instant-execution-summary__state span {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.instant-execution-summary__stats {
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0;
}

.instant-execution-summary__stats > div {
  align-items: baseline;
  gap: var(--space-1);
}

.instant-execution-summary__stats dt {
  color: var(--text-secondary);
}

.instant-execution-summary__stats dd {
  margin: 0;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

@media (max-width: 1280px) {
  .instant-execution-summary__lower {
    align-items: flex-end;
    flex-direction: column;
  }
}
</style>
