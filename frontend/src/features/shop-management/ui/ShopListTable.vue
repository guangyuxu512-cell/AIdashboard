<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import {
  SHOP_PLATFORM_META,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  rows: ShopListItemViewModel[]
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  view: [shop: ShopListItemViewModel]
  edit: [shop: ShopListItemViewModel]
  retry: []
}>()

const columns: DataTableColumns<ShopListItemViewModel> = [
  {
    title: '店铺名称',
    key: 'shopName',
    width: 190,
    ellipsis: { tooltip: true },
  },
  {
    title: '平台',
    key: 'platform',
    width: 90,
    render: (shop) => SHOP_PLATFORM_META[shop.platform].label,
  },
  { title: '负责人', key: 'ownerName', width: 90 },
  {
    title: '店铺状态',
    key: 'enabledStatus',
    width: 110,
    render: (shop) =>
      h(ShopStatusTag, { category: 'shop', status: shop.enabledStatus }),
  },
  {
    title: '会话状态',
    key: 'sessionStatus',
    width: 110,
    render: (shop) =>
      h(ShopStatusTag, { category: 'session', status: shop.sessionStatus }),
  },
  {
    title: '执行设备',
    key: 'executionDeviceName',
    width: 160,
    ellipsis: { tooltip: true },
    render: (shop) => shop.executionDeviceName ?? '—',
  },
  {
    title: '自动化状态',
    key: 'automationStatus',
    width: 120,
    render: (shop) =>
      h(ShopStatusTag, {
        category: 'automation',
        status: shop.automationStatus,
      }),
  },
  { title: '今日 GMV', key: 'todayGmvDisplay', width: 130, align: 'right' },
  { title: '更新时间', key: 'updatedAtDisplay', width: 150 },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    fixed: 'right',
    render: (shop) =>
      h('div', { class: 'shop-list-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('view', shop) },
          () => '查看',
        ),
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('edit', shop) },
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
    :row-key="(row: ShopListItemViewModel) => row.shopId"
    :scroll-x="1290"
    empty-description="没有符合当前条件的店铺"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
:deep(.shop-list-table__actions) {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
