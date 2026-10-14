<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NTooltip, useMessage, type DataTableRowKey } from 'naive-ui'
import {
  ManagementListSection,
  PaginationBar,
  StatusTag,
  TableToolbar,
} from '@/shared/components'
import { AppButton } from '@/shared/ui'
import { productDataKeys } from '../api/query-keys'
import { PRODUCT_DATA_UNAVAILABLE } from '../api/product-data-source'
import { readProductColumns } from '../model/column-preferences'
import { emptyProductFilters, productPeriod } from '../model/query'
import type {
  ProductDataQuery,
  ProductDataRow,
  ProductDataSource,
} from '../model/types'
import ProductDataFilterBar from './ProductDataFilterBar.vue'
import ProductDataTable from './ProductDataTable.vue'
import ProductFieldConfigDialog from './ProductFieldConfigDialog.vue'
import ProductGroupManagerDialog from './ProductGroupManagerDialog.vue'
import ProductBatchGroupDialog from './ProductBatchGroupDialog.vue'
import ProductDataDetailDrawer from './ProductDataDetailDrawer.vue'

const props = defineProps<{
  source: ProductDataSource
  contextKey: string
  userId: string | null
}>()
const message = useMessage()
const draft = ref(emptyProductFilters())
const params = ref<ProductDataQuery>({
  filters: emptyProductFilters(),
  period: productPeriod(emptyProductFilters()),
  page: 1,
  pageSize: 10,
  sort: null,
})
const checked = ref<DataTableRowKey[]>([]),
  detail = ref<ProductDataRow | null>(null)
const fieldsShow = ref(false),
  managerShow = ref(false),
  batchShow = ref(false)
const visibleColumns = ref(readProductColumns(props.userId))
const query = useQuery({
  queryKey: computed(() =>
    productDataKeys.list(props.contextKey, params.value),
  ),
  queryFn: ({ queryKey }) => props.source.list(queryKey[3] as ProductDataQuery),
  retry: false,
})
const groups = useQuery({
  queryKey: computed(() =>
    productDataKeys.groups(props.contextKey, draft.value.shopId),
  ),
  enabled: computed(() => props.source.available && !!draft.value.shopId),
  queryFn: ({ queryKey }) => props.source.groups(String(queryKey[3])),
  retry: false,
})
const rows = computed(() => query.data.value?.items ?? [])
const selectedRows = computed(() =>
  rows.value.filter((row) => checked.value.includes(row.id)),
)
const batchShopId = computed(() => {
  const ids = new Set(selectedRows.value.map((row) => row.shopId))
  return ids.size === 1 ? selectedRows.value[0]!.shopId : null
})
const batchReason = computed(() =>
  !props.source.available
    ? PRODUCT_DATA_UNAVAILABLE
    : !selectedRows.value.length
      ? '请先勾选商品'
      : !batchShopId.value
        ? '请只勾选同一店铺的商品'
        : null,
)
watch(
  () => draft.value.shopId,
  () => {
    draft.value.groupId = null
    checked.value = []
    managerShow.value = false
    batchShow.value = false
    detail.value = null
  },
)
watch(
  () => params.value.page,
  () => {
    checked.value = []
    detail.value = null
  },
)
watch(
  () => query.data.value?.page,
  (page) => {
    if (page && page !== params.value.page)
      params.value = { ...params.value, page }
  },
)
function apply() {
  try {
    const next: ProductDataQuery = {
      ...params.value,
      filters: {
        ...draft.value,
        customDateRange: draft.value.customDateRange
          ? [...draft.value.customDateRange]
          : null,
      },
      period: productPeriod(draft.value),
      page: 1,
    }
    const unchanged = JSON.stringify(next) === JSON.stringify(params.value)
    params.value = next
    checked.value = []
    detail.value = null
    if (unchanged) void query.refetch()
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '筛选条件无效')
  }
}
function reset() {
  draft.value = emptyProductFilters()
  apply()
}
function sort(value: ProductDataQuery['sort']) {
  checked.value = []
  detail.value = null
  params.value = { ...params.value, sort: value, page: 1 }
}
function pageSize(value: number) {
  checked.value = []
  params.value = { ...params.value, pageSize: value, page: 1 }
}
function groupDeleted(id: string) {
  if (draft.value.groupId === id) draft.value.groupId = null
  if (params.value.filters.groupId === id)
    params.value = {
      ...params.value,
      filters: { ...params.value.filters, groupId: null },
      page: 1,
    }
  checked.value = []
  detail.value = null
}
function columnsSaved(columns: typeof visibleColumns.value) {
  visibleColumns.value = [...columns]
  if (params.value.sort && !columns.includes(params.value.sort.field))
    sort(null)
}
function batchSaved() {
  checked.value = []
  detail.value = null
}
</script>

<template>
  <ManagementListSection class="product-data-view">
    <TableToolbar>
      <StatusTag v-if="source.mode === 'mock'" label="演示数据" />
      <span v-if="checked.length" class="product-data-view__selected"
        >已选 {{ checked.length }} 件</span
      >
      <template #actions>
        <NTooltip :disabled="source.available && !!draft.shopId">
          <template #trigger
            ><span
              ><AppButton
                :disabled="!source.available || !draft.shopId"
                @click="managerShow = true"
                >分组管理</AppButton
              ></span
            ></template
          >
          {{ source.available ? '请先选择店铺' : PRODUCT_DATA_UNAVAILABLE }}
        </NTooltip>
        <NTooltip :disabled="!batchReason">
          <template #trigger
            ><span
              ><AppButton
                :disabled="!!batchReason || query.isFetching.value"
                @click="batchShow = true"
                >批量设置分组</AppButton
              ></span
            ></template
          >
          {{ batchReason }}
        </NTooltip>
      </template>
    </TableToolbar>
    <ProductDataFilterBar
      v-model="draft"
      :groups="groups.data.value ?? []"
      :groups-loading="!!draft.shopId && groups.isFetching.value"
      :groups-error="!!draft.shopId && !!groups.error.value"
      :enabled="source.available"
      :loading="query.isFetching.value"
      @query="apply"
      @reset="reset"
      @fields="fieldsShow = true"
      @retry-groups="groups.refetch()"
    />
    <ProductDataTable
      :rows="rows"
      :visible-columns="visibleColumns"
      :checked="checked"
      :sort="params.sort"
      :enabled="source.available"
      :loading="query.isFetching.value"
      :error="
        query.error.value
          ? query.error.value instanceof Error
            ? query.error.value.message
            : '商品数据读取失败'
          : null
      "
      @update:checked="checked = $event"
      @update:sort="sort"
      @retry="query.refetch()"
      @detail="detail = $event"
    />
    <PaginationBar
      v-if="query.data.value"
      :page="params.page"
      :page-size="params.pageSize"
      :item-count="query.data.value?.total ?? 0"
      @update:page="params = { ...params, page: $event }"
      @update:page-size="pageSize"
    />
    <ProductFieldConfigDialog
      v-model:show="fieldsShow"
      :columns="visibleColumns"
      :user-id="userId"
      @saved="columnsSaved"
    />
    <ProductGroupManagerDialog
      v-if="draft.shopId"
      v-model:show="managerShow"
      :shop-id="draft.shopId"
      :source="source"
      :context-key="contextKey"
      @deleted="groupDeleted"
    />
    <ProductBatchGroupDialog
      v-if="batchShopId"
      v-model:show="batchShow"
      :shop-id="batchShopId"
      :rows="selectedRows"
      :source="source"
      :context-key="contextKey"
      @saved="batchSaved"
    />
    <ProductDataDetailDrawer
      :show="!!detail"
      :row="detail"
      @update:show="detail = null"
    />
  </ManagementListSection>
</template>

<style scoped>
.product-data-view__selected {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
</style>
