<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import {
  DeviceEnabledStatusTag,
  DeviceStatusTag,
  type DeviceListItemViewModel,
} from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  rows: DeviceListItemViewModel[]
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  view: [device: DeviceListItemViewModel]
  edit: [device: DeviceListItemViewModel]
  retry: []
}>()

const columns: DataTableColumns<DeviceListItemViewModel> = [
  {
    title: '设备名称',
    key: 'deviceName',
    width: 170,
    ellipsis: { tooltip: true },
  },
  {
    title: '启用状态',
    key: 'enabledStatus',
    width: 90,
    render: (device) =>
      h(DeviceEnabledStatusTag, { status: device.enabledStatus }),
  },
  {
    title: '运行状态',
    key: 'runtimeStatus',
    width: 100,
    render: (device) => h(DeviceStatusTag, { status: device.runtimeStatus }),
  },
  {
    title: '标签 / 位置',
    key: 'location',
    width: 180,
    render: (device) =>
      h('div', { class: 'device-table__location' }, [
        h('span', device.location),
        h('small', device.tags.join(' · ')),
      ]),
  },
  { title: '系统', key: 'systemDisplay', width: 120 },
  { title: 'Worker 版本', key: 'workerVersionDisplay', width: 130 },
  {
    title: '当前任务',
    key: 'currentTaskName',
    width: 180,
    ellipsis: { tooltip: true },
    render: (device) =>
      device.runtimeStatus === 'unavailable'
        ? '未接入'
        : (device.currentTaskName ?? '空闲'),
  },
  { title: 'CPU', key: 'cpuUsageDisplay', width: 80, align: 'right' },
  { title: '内存', key: 'memoryUsageDisplay', width: 80, align: 'right' },
  { title: '最后心跳', key: 'lastHeartbeatAtDisplay', width: 165 },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    fixed: 'right',
    render: (device) =>
      h('div', { class: 'device-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('view', device) },
          () => '查看',
        ),
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('edit', device) },
          () => '编辑',
        ),
      ]),
  },
]
</script>

<template>
  <DataTable
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: DeviceListItemViewModel) => row.deviceId"
    :scroll-x="1435"
    empty-description="没有符合当前条件的设备"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
:deep(.device-table__location) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

:deep(.device-table__location small) {
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}

:deep(.device-table__actions) {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
