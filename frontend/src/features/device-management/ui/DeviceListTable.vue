<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

import {
  DeviceConnectionStatusTag,
  DeviceEnabledStatusTag,
  DeviceIdentity,
  YingdaoAvailabilityStatusTag,
} from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import type { DeviceManagementRowViewModel } from '../model/types'

defineProps<{
  rows: DeviceManagementRowViewModel[]
  loading?: boolean
  error?: string | null
  checkedRowKeys?: DataTableRowKey[]
}>()

const emit = defineEmits<{
  view: [device: DeviceManagementRowViewModel]
  edit: [device: DeviceManagementRowViewModel]
  retry: []
  'update:checkedRowKeys': [keys: DataTableRowKey[]]
}>()

function centered(children: unknown) {
  return h('div', { class: 'device-table__center' }, children as never)
}

const columns: DataTableColumns<DeviceManagementRowViewModel> = [
  { type: 'selection', width: 44, fixed: 'left' },
  {
    title: '设备名称',
    key: 'deviceName',
    width: 190,
    fixed: 'left',
    render: (device) => h(DeviceIdentity, { name: device.deviceName }),
  },
  {
    title: '在线状态',
    key: 'runtimeStatus',
    width: 90,
    align: 'center',
    render: (device) =>
      centered(h(DeviceConnectionStatusTag, { status: device.runtimeStatus })),
  },
  {
    title: '当前执行',
    key: 'currentExecution',
    width: 190,
    align: 'center',
    render: (device) =>
      centered(
        h('div', { class: 'device-table__execution' }, [
          h(StatusTag, {
            label: device.currentExecution.label,
            tone: device.currentExecution.tone,
          }),
          device.currentExecution.name
            ? h('small', device.currentExecution.name)
            : null,
        ]),
      ),
  },
  {
    title: '影刀',
    key: 'yingdao',
    width: 86,
    align: 'center',
    render: (device) =>
      centered(
        h(YingdaoAvailabilityStatusTag, {
          status: device.yingdaoInventory?.availabilityStatus ?? 'not_detected',
        }),
      ),
  },
  {
    title: '影刀账号',
    key: 'yingdaoAccount',
    width: 120,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (device) => device.yingdaoInventory?.accountDisplay ?? '—',
  },
  {
    title: '本机已同步应用',
    key: 'applicationCount',
    width: 130,
    align: 'center',
    render: (device) => device.yingdaoInventory?.applicationCount ?? '—',
  },
  {
    title: '绑定店铺',
    key: 'boundShopCount',
    width: 90,
    align: 'center',
    render: (device) => device.boundShopCount ?? '—',
  },
  {
    title: '最后心跳',
    key: 'lastHeartbeatAtDisplay',
    width: 120,
    align: 'center',
  },
  {
    title: '启用',
    key: 'enabledStatus',
    width: 88,
    align: 'center',
    render: (device) =>
      centered(h(DeviceEnabledStatusTag, { status: device.enabledStatus })),
  },
  {
    title: '操作',
    key: 'actions',
    width: 116,
    align: 'center',
    fixed: 'right',
    render: (device) =>
      centered(
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
      ),
  },
]
</script>

<template>
  <DataTable
    class="device-list-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: DeviceManagementRowViewModel) => row.deviceId"
    :scroll-x="1254"
    :checked-row-keys="checkedRowKeys"
    appearance="list"
    viewport="fill"
    empty-description="没有符合当前条件的设备"
    @update:checked-row-keys="$emit('update:checkedRowKeys', $event)"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.device-list-table {
  min-height: 0;
  flex: 1;
}

:deep(.device-table__center) {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
}

:deep(.device-table__execution) {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

:deep(.device-table__execution small) {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.device-table__actions) {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
