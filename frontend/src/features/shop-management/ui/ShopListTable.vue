<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

import {
  getShopExecutionDeviceSummary,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import { PlatformDisplay } from '@/entities/platform'
import { ShopSessionStatusTag } from '@/entities/shop-session'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  rows: ShopListItemViewModel[]
  loading?: boolean
  error?: string | null
  checkedRowKeys?: string[]
  statusChangingShopId?: string | null
}>()

const emit = defineEmits<{
  view: [shop: ShopListItemViewModel]
  'toggle-enabled': [shop: ShopListItemViewModel]
  remove: [shop: ShopListItemViewModel]
  retry: []
  'update:checkedRowKeys': [keys: string[]]
}>()

const columns: DataTableColumns<ShopListItemViewModel> = [
  { type: 'selection', width: 46 },
  {
    title: '店铺名称',
    key: 'shopName',
    width: 160,
    align: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: '平台',
    key: 'platform',
    width: 96,
    align: 'center',
    render: (shop) => h(PlatformDisplay, { code: shop.platform }),
  },
  {
    title: '登录状态',
    key: 'loginStatus',
    width: 96,
    align: 'center',
    render: (shop) => h(ShopSessionStatusTag, { status: shop.loginStatus }),
  },
  {
    title: '负责人',
    key: 'ownerName',
    width: 82,
    align: 'center',
  },
  {
    title: '执行设备',
    key: 'executionDeviceNames',
    width: 148,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (shop) => {
      const summary = getShopExecutionDeviceSummary(shop)
      return h('span', { title: summary.names.join('、') }, summary.label)
    },
  },
  {
    title: '店铺状态',
    key: 'enabledStatus',
    width: 96,
    align: 'center',
    render: (shop) => h(ShopStatusTag, { status: shop.enabledStatus }),
  },
  {
    title: '备注',
    key: 'note',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (shop) => shop.note || '—',
  },
  {
    title: '操作',
    key: 'actions',
    width: 184,
    align: 'center',
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
          {
            tone: 'text',
            loading: props.statusChangingShopId === shop.shopId,
            disabled:
              Boolean(props.statusChangingShopId) &&
              props.statusChangingShopId !== shop.shopId,
            onClick: () => emit('toggle-enabled', shop),
          },
          () => (shop.enabled ? '停用' : '启用'),
        ),
        h(
          AppButton,
          {
            tone: 'text',
            onClick: () => emit('remove', shop),
          },
          () => '移除',
        ),
      ]),
  },
]

function updateCheckedRowKeys(keys: DataTableRowKey[]): void {
  emit(
    'update:checkedRowKeys',
    keys.map((key) => String(key)),
  )
}
</script>

<template>
  <DataTable
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: ShopListItemViewModel) => row.shopId"
    :scroll-x="1058"
    :checked-row-keys="checkedRowKeys"
    appearance="list"
    viewport="fill"
    class="shop-list-table"
    empty-description="没有符合当前条件的店铺"
    @retry="$emit('retry')"
    @update:checked-row-keys="updateCheckedRowKeys"
  />
</template>

<style scoped>
.shop-list-table {
  min-height: 0;
  flex: 1;
}

:deep(.shop-list-table__actions) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  white-space: nowrap;
}
</style>
