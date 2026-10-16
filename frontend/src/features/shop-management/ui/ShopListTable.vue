<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

import {
  getShopExecutionDeviceSummary,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import { PlatformDisplay } from '@/entities/platform'
import { supportsShopLogin } from '../model/useShopLogin'
import type { ShopLoginFeedback } from '../model/useShopLogin'
import { ShopSessionStatusTag } from '@/entities/shop-session'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  rows: ShopListItemViewModel[]
  loading?: boolean
  error?: string | null
  checkedRowKeys?: string[]
  statusChangingShopId?: string | null
  showOwner?: boolean
  showDeviceSummary?: boolean
  canLogin?: boolean
  loginFeedback?: ReadonlyMap<string, ShopLoginFeedback>
}>()

const emit = defineEmits<{
  view: [shop: ShopListItemViewModel]
  login: [shop: ShopListItemViewModel]
  'toggle-enabled': [shop: ShopListItemViewModel]
  remove: [shop: ShopListItemViewModel]
  retry: []
  'update:checkedRowKeys': [keys: string[]]
}>()

const columns = computed<DataTableColumns<ShopListItemViewModel>>(() => [
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
  ...(props.showOwner
    ? [
        {
          title: '负责人',
          key: 'ownerName',
          width: 82,
          align: 'center' as const,
        },
      ]
    : []),
  ...(props.showDeviceSummary
    ? [
        {
          title: '执行设备',
          key: 'executionDeviceNames',
          width: 148,
          align: 'center' as const,
          ellipsis: { tooltip: true },
          render: (shop: ShopListItemViewModel) => {
            const summary = getShopExecutionDeviceSummary(shop)
            return h('span', { title: summary.names.join('、') }, summary.label)
          },
        },
      ]
    : []),
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
    width: props.canLogin ? 240 : 184,
    align: 'center',
    fixed: 'right',
    render: (shop) =>
      h('div', { class: 'shop-list-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('view', shop) },
          () => '查看',
        ),
        ...(props.canLogin && supportsShopLogin(shop.platform)
          ? [
              h(
                AppButton,
                {
                  tone: 'text',
                  loading: Boolean(
                    props.loginFeedback?.get(shop.shopId)?.opening ||
                    props.loginFeedback?.get(shop.shopId)?.focusing,
                  ),
                  disabled: Boolean(
                    props.loginFeedback?.get(shop.shopId)?.opening ||
                    props.loginFeedback?.get(shop.shopId)?.focusing,
                  ),
                  title:
                    props.loginFeedback?.get(shop.shopId)?.error ??
                    props.loginFeedback?.get(shop.shopId)?.status ??
                    undefined,
                  onClick: () => emit('login', shop),
                },
                () =>
                  props.loginFeedback?.get(shop.shopId)?.opening
                    ? '打开中…'
                    : props.loginFeedback?.get(shop.shopId)?.retryReady ||
                        props.loginFeedback?.get(shop.shopId)?.retryBlocked
                      ? '登录'
                      : props.loginFeedback?.get(shop.shopId)?.busy
                        ? '登录中…'
                        : '登录',
              ),
            ]
          : []),
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
])

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
    :scroll-x="canLogin ? 1114 : 1058"
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
