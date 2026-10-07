<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import {
  type DataTableColumns,
  type DataTableRowKey,
  type DataTableSortState,
  useMessage,
} from 'naive-ui'
import dayjs from 'dayjs'
import ShopSelector from '@/entities/shop/ui/ShopSelector.vue'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
} from '@/shared/components'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import type {
  CandidateQuery,
  SelectionCandidate,
  SelectionService,
} from '../model/contracts'
import ExternalProductImage from './ExternalProductImage.vue'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const message = useMessage()
const filters = ref<CandidateQuery>({
  page: 1,
  pageSize: 20,
  shopId: null,
  keyword: '',
  blocked: false,
  sortField: null,
  sortOrder: false,
})
const keyword = ref(''),
  checked = ref<DataTableRowKey[]>([]),
  detailId = ref<string | null>(null),
  busy = ref(false)
const query = useQuery({
  queryKey: computed(() => [
    'selection-candidates',
    props.contextKey,
    { ...filters.value },
  ]),
  queryFn: ({ queryKey }) =>
    props.service.candidates(queryKey[2] as CandidateQuery),
  retry: false,
  placeholderData: keepPreviousData,
})
const search = useAutoSearch(() => {
  filters.value = { ...filters.value, keyword: keyword.value.trim(), page: 1 }
  checked.value = []
})
function filterChanged() {
  search.cancel()
  filters.value.page = 1
  checked.value = []
}
function setBlocked(value: string | number | null) {
  filters.value.blocked = value === 'blocked'
  filterChanged()
}
function reset() {
  keyword.value = ''
  filters.value.shopId = null
  filters.value.blocked = false
  search.submitNow()
}
function setPage(value: number) {
  filters.value.page = value
  checked.value = []
}
function setPageSize(value: number) {
  filters.value.pageSize = value
  filterChanged()
}
watch(
  () => query.data.value?.page,
  (page) => {
    if (page && filters.value.page !== page) filters.value.page = page
  },
)
async function act(
  row: SelectionCandidate,
  action: 'collect' | 'block' | 'restore',
) {
  if (busy.value) return
  busy.value = true
  try {
    const receipt = await props.service.demoAction(row.id, action)
    message.info(receipt.message)
    checked.value = []
    await query.refetch()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '演示操作失败')
  } finally {
    busy.value = false
  }
}
function sort(state: DataTableSortState | DataTableSortState[] | null) {
  const value = Array.isArray(state) ? state[0] : state
  const field = value?.columnKey
  const order = value?.order
  filters.value = {
    ...filters.value,
    sortField:
      (field === 'listedAt' || field === 'negativeReviewRate') && order
        ? field
        : null,
    sortOrder: order || false,
    page: 1,
  }
  checked.value = []
}
const columns = computed<DataTableColumns<SelectionCandidate>>(() => [
  { type: 'selection', width: 44, fixed: 'left', align: 'center' },
  {
    key: 'shopName',
    title: '店铺名',
    width: 140,
    fixed: 'left',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'image',
    title: '图片',
    width: 64,
    fixed: 'left',
    align: 'center',
    render: (row) =>
      h(ExternalProductImage, { src: row.imageUrl, title: row.title }),
  },
  {
    key: 'title',
    title: '标题',
    width: 220,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'productId',
    title: '商品ID',
    width: 220,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'category',
    title: '类目',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'priceBand',
    title: '价格带',
    width: 100,
    align: 'center',
    render: (row) => row.priceBand ?? '—',
  },
  {
    key: 'listedAt',
    title: '上架日期',
    width: 140,
    align: 'center',
    sorter: true,
    sortOrder:
      filters.value.sortField === 'listedAt' ? filters.value.sortOrder : false,
    render: (row) =>
      row.listedAt ? dayjs(row.listedAt).format('YYYY-MM-DD') : '—',
  },
  {
    key: 'negativeReviewRate',
    title: '差评率',
    width: 100,
    align: 'center',
    sorter: true,
    sortOrder:
      filters.value.sortField === 'negativeReviewRate'
        ? filters.value.sortOrder
        : false,
    render: (row) =>
      row.negativeReviewRate === null
        ? '—'
        : `${(row.negativeReviewRate * 100).toFixed(2)}%`,
  },
  {
    key: 'actions',
    title: '操作',
    width: 200,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h('div', { class: 'selection-row-actions' }, [
        h(
          AppButton,
          {
            tone: 'text',
            onClick: () => {
              detailId.value = row.id
            },
          },
          () => '详情',
        ),
        h(
          AppButton,
          {
            tone: 'text',
            disabled: busy.value,
            onClick: () => act(row, 'collect'),
          },
          () => '采集入库',
        ),
        h(
          AppButton,
          {
            tone: 'text',
            disabled: busy.value,
            onClick: () => act(row, row.blocked ? 'restore' : 'block'),
          },
          () => (row.blocked ? '恢复' : '屏蔽'),
        ),
      ]),
  },
])
</script>

<template>
  <div class="selection-panel">
    <FilterBar>
      <FilterField width="md"
        ><ShopSelector
          v-model="filters.shopId"
          placeholder="全部店铺"
          @update:model-value="filterChanged"
      /></FilterField>
      <FilterField width="lg"
        ><AppInput
          v-model="keyword"
          placeholder="搜索标题或商品ID"
          aria-label="搜索候选商品"
          clearable
          @update:model-value="search.onInput"
          @compositionstart="search.onCompositionStart"
          @compositionend="search.onCompositionEnd(keyword)"
          @keydown.enter="search.onEnter"
      /></FilterField>
      <FilterField width="sm"
        ><AppSelect
          :model-value="filters.blocked ? 'blocked' : 'normal'"
          :options="[
            { label: '未屏蔽', value: 'normal' },
            { label: '已屏蔽', value: 'blocked' },
          ]"
          @update:model-value="setBlocked"
      /></FilterField>
      <template #actions
        ><AppButton @click="reset">重置</AppButton
        ><AppButton @click="query.refetch()">刷新</AppButton></template
      >
    </FilterBar>
    <ManagementListSection>
      <DataTable
        :columns="columns"
        :data="query.data.value?.items ?? []"
        :loading="query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="1478"
        viewport="fill"
        appearance="list"
        :checked-row-keys="checked"
        empty-description="暂无候选商品"
        @update:checked-row-keys="checked = $event"
        @retry="query.refetch()"
        @update:sorter="sort"
      />
      <PaginationBar
        :page="filters.page"
        :page-size="filters.pageSize"
        :item-count="query.data.value?.total ?? 0"
        @update:page="setPage"
        @update:page-size="setPageSize"
      />
    </ManagementListSection>
    <CandidateDetailDrawer
      :id="detailId"
      :service="service"
      :context-key="contextKey"
      @close="detailId = null"
    />
  </div>
</template>
