<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

import {
  getShopExecutionDeviceSummary,
  type ShopListItemViewModel,
} from '@/entities/shop'
import { PlatformDisplay } from '@/entities/platform'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

defineProps<{
  rows: ShopListItemViewModel[]
  loading?: boolean
  error?: string | null
  checkedRowKeys?: string[]
}>()

const emit = defineEmits<{
  view: [shop: ShopListItemViewModel]
  retry: []
  'update:checkedRowKeys': [keys: string[]]
}>()

const columns: DataTableColumns<ShopListItemViewModel> = [
  { type: 'selection', width: 46 },
  {
    title: '店铺名称',
    key: 'shopName',
    width: 160,
    align: 'center',
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
    title: '负责人',
    key: 'ownerName',
    width: 82,
    align: 'center',
  },
  {
    title: '执行设备',
    key: 'executionDeviceName',
    width: 148,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (shop) => {
      const summary = getShopExecutionDeviceSummary(shop)
      return h('span', { title: summary.names.join('、') }, summary.label)
    },
  },
  {
    title: '开启',
    key: 'automationPlaceholder',
    width: 80,
    align: 'center',
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
            title: '店铺自动化总开关尚未接入',
            'aria-label': `${shop.shopName}自动化总开关尚未接入`,
          }),
        ],
      ),
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
    width: 112,
    align: 'center',
    fixed: 'right',
    render: (shop) =>
      h(
        'div',
        { class: 'shop-list-table__actions' },
        [
          h(
            AppButton,
            { tone: 'text', onClick: () => emit('view', shop) },
            () => '查看',
          ),
          h(
            AppButton,
            {
              tone: 'text',
              disabled: true,
              title: '店铺删除 API 尚未接入',
            },
            () => '删除',
          ),
        ],
      ),
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
    :scroll-x="874"
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

:deep(.shop-list-table__automation-placeholder) {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  white-space: nowrap;
}

:deep(.shop-list-table__actions) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  white-space: nowrap;
}
</style>
