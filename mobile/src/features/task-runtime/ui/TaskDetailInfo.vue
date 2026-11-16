<script setup lang="ts">
import { computed } from 'vue'

import type { TaskReadDto } from '@/entities/task'

import { formatTaskDateTime } from '../model/runtime-display'
import type { TaskDetailDeviceState } from '../model/task-detail-display'

const props = defineProps<{
  task: TaskReadDto
  deviceName?: string | null
  deviceState: TaskDetailDeviceState
}>()

interface TaskDetailInfoRow {
  key: 'started' | 'device' | 'result' | 'error'
  label: string
  value: string
}

const deviceValue = computed(() => {
  if (props.deviceState === 'loading') return '加载中'
  if (props.deviceState === 'error') return '暂时无法加载'
  return props.deviceName?.trim() || '设备未命名'
})

const rows = computed<TaskDetailInfoRow[]>(() => {
  const items: TaskDetailInfoRow[] = []
  if (props.task.started_at) {
    items.push({
      key: 'started',
      label: '开始时间',
      value: formatTaskDateTime(props.task.started_at),
    })
  }

  items.push({
    key: 'device',
    label: '执行设备',
    value: deviceValue.value,
  })

  const resultSummary = props.task.result?.summary
  if (
    props.task.status === 'success' &&
    typeof resultSummary === 'string' &&
    resultSummary.trim()
  ) {
    items.push({
      key: 'result',
      label: '执行结果',
      value: resultSummary.trim(),
    })
  }

  if (
    (props.task.status === 'failed' || props.task.status === 'lost') &&
    props.task.error_message?.trim()
  ) {
    items.push({
      key: 'error',
      label: '失败原因',
      value: props.task.error_message.trim(),
    })
  }
  return items
})
</script>

<template>
  <dl class="task-detail-info" data-testid="task-detail-info">
    <div
      v-for="row in rows"
      :key="row.key"
      class="task-detail-info__row"
      :data-testid="`task-detail-info-${row.key}`"
    >
      <dt>{{ row.label }}</dt>
      <dd :title="row.value">{{ row.value }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.task-detail-info {
  min-width: 0;
  margin: 0;
}

.task-detail-info__row {
  display: grid;
  min-width: 0;
  min-height: var(--touch-target-min);
  padding-inline: var(--visual-v2-business-card-padding-left)
    var(--visual-v2-business-card-padding-right);
  border-top: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-divider-color);
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  align-items: center;
}

.task-detail-info dt,
.task-detail-info dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: var(--typography-v2-meta-size);
  line-height: var(--typography-v2-detail-hero-meta-line-height);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-detail-info dt {
  color: var(--visual-v2-detail-meta-color);
  font-weight: var(--typography-v2-meta-weight);
}

.task-detail-info dd {
  color: var(--visual-v2-page-text-primary);
  font-weight: var(--typography-v2-status-weight);
  text-align: right;
}
</style>
