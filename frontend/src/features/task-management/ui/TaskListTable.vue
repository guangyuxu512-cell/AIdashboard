<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import { TaskStatusTag, type TaskListItemViewModel } from '@/entities/task'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  rows: TaskListItemViewModel[]
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  detail: [task: TaskListItemViewModel]
  retry: []
}>()

const columns: DataTableColumns<TaskListItemViewModel> = [
  {
    title: '状态',
    key: 'status',
    width: 90,
    align: 'center',
    render: (task) =>
      h('div', { class: 'task-table__center' }, [
        h(TaskStatusTag, { status: task.status }),
      ]),
  },
  {
    title: '执行对象',
    key: 'executionName',
    width: 240,
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
    title: '进度',
    key: 'progressDisplay',
    width: 95,
    align: 'center',
  },
  {
    title: '当前信息',
    key: 'currentMessage',
    width: 260,
    ellipsis: { tooltip: true },
  },
  {
    title: '开始时间',
    key: 'startedAtDisplay',
    width: 165,
    align: 'center',
  },
  {
    title: '操作',
    key: 'actions',
    width: 70,
    align: 'center',
    fixed: 'right',
    render: (task) =>
      h(
        'div',
        { class: 'task-table__center' },
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('detail', task) },
          () => '详情',
        ),
      ),
  },
]
</script>

<template>
  <DataTable
    class="task-list-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: TaskListItemViewModel) => row.taskId"
    :scroll-x="1070"
    appearance="list"
    viewport="fill"
    empty-description="暂无任务，当前还没有自动化执行记录。"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.task-list-table {
  min-height: 0;
  flex: 1;
}

:deep(.task-table__center) {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
</style>
