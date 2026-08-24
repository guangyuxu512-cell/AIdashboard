<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import { h } from 'vue'

import { type ScheduleListItemViewModel } from '@/entities/schedule'
import { TaskStatusTag } from '@/entities/task'
import DataTable from '@/shared/components/DataTable.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

defineProps<{
  rows: ScheduleListItemViewModel[]
  loading?: boolean
  error?: string | null
  statusChanging?: boolean
}>()

const emit = defineEmits<{
  detail: [schedule: ScheduleListItemViewModel]
  toggle: [schedule: ScheduleListItemViewModel]
  retry: []
}>()

const columns: DataTableColumns<ScheduleListItemViewModel> = [
  {
    title: '计划名称',
    key: 'name',
    width: 190,
    ellipsis: { tooltip: true },
  },
  {
    title: '执行对象',
    key: 'executionName',
    width: 190,
    ellipsis: { tooltip: true },
  },
  {
    title: '设备',
    key: 'deviceName',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '触发规则',
    key: 'triggerRuleDisplay',
    width: 115,
    align: 'center',
  },
  {
    title: '下次执行',
    key: 'nextRunAtDisplay',
    width: 165,
    align: 'center',
  },
  {
    title: '最近执行',
    key: 'latestRun',
    width: 105,
    align: 'center',
    render: (schedule) => {
      if (schedule.latestRun?.taskStatus) {
        return h(TaskStatusTag, { status: schedule.latestRun.taskStatus })
      }
      if (schedule.latestRun?.triggerResult === 'blocked') {
        return h(StatusTag, { label: '触发失败', tone: 'error' })
      }
      return '—'
    },
  },
  {
    title: '开启',
    key: 'enabled',
    width: 80,
    align: 'center',
    render: (schedule) =>
      h(AppSwitch, {
        modelValue: schedule.enabled,
        'onUpdate:modelValue': () => emit('toggle', schedule),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render: (schedule) =>
      h('div', { class: 'schedule-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('detail', schedule) },
          () => '查看',
        ),
      ]),
  },
]
</script>

<template>
  <DataTable
    class="schedule-list-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: ScheduleListItemViewModel) => row.scheduleId"
    :scroll-x="1075"
    appearance="list"
    viewport="fill"
    empty-description="暂无定时计划"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.schedule-list-table {
  min-height: 0;
  flex: 1;
}

:deep(.schedule-table__actions) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  white-space: nowrap;
}
</style>
