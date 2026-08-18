<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import {
  ShopPlatformDisplay,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

defineProps<{
  rows: ShopListItemViewModel[]
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  view: [shop: ShopListItemViewModel]
  retry: []
}>()

const columns: DataTableColumns<ShopListItemViewModel> = [
  {
    title: '店铺名称',
    key: 'shopName',
    width: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: '平台',
    key: 'platform',
    width: 110,
    render: (shop) => h(ShopPlatformDisplay, { platform: shop.platform }),
  },
  { title: '负责人', key: 'ownerName', width: 86 },
  {
    title: '执行设备',
    key: 'executionDeviceName',
    width: 170,
    ellipsis: { tooltip: true },
    render: (shop) => shop.executionDeviceName ?? '未分配',
  },
  {
    title: '开启',
    key: 'automationPlaceholder',
    width: 108,
    render: (shop) =>
      h(
        'div',
        {
          class: 'shop-list-table__automation-placeholder',
          title: '自动化控制尚未接入',
        },
        [
          h(AppSwitch, {
            modelValue: false,
            disabled: true,
            'aria-label': `${shop.shopName}自动化尚未接入`,
          }),
          h('span', '未接入'),
        ],
      ),
  },
  {
    title: '状态',
    key: 'enabledStatus',
    width: 100,
    render: (shop) => h(ShopStatusTag, { status: shop.enabledStatus }),
  },
  {
    title: '备注',
    key: 'note',
    width: 180,
    ellipsis: { tooltip: true },
    render: (shop) => shop.note || '—',
  },
  {
    title: '操作',
    key: 'actions',
    width: 74,
    fixed: 'right',
    render: (shop) =>
      h(
        AppButton,
        { tone: 'text', onClick: () => emit('view', shop) },
        () => '查看',
      ),
  },
]
</script>

<template>
  <DataTable
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: ShopListItemViewModel) => row.shopId"
    :scroll-x="1008"
    empty-description="没有符合当前条件的店铺"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
:deep(.shop-list-table__automation-placeholder) {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  white-space: nowrap;
}
</style>
