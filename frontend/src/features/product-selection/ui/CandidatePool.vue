<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { Copy } from '@lucide/vue'
import {
  type DataTableColumns,
  type DataTableRowKey,
  type DataTableSortState,
  NText,
  NEllipsis,
  NAlert,
  useMessage,
} from 'naive-ui'
import ShopSelector from '@/entities/shop/ui/ShopSelector.vue'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
  TableToolbar,
} from '@/shared/components'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import type {
  CandidateQuery,
  SelectionCandidate,
  SelectionService,
  BatchCollectReceipt,
} from '../model/contracts'
import {
  formatCandidateDate,
  formatReviewRate,
} from '../model/candidate-display'
import ExternalProductImage from './ExternalProductImage.vue'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const message = useMessage()
const filters = ref<CandidateQuery>({
  page: 1,
  pageSize: 10,
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
const batchReceipt = ref<BatchCollectReceipt | null>(null)
const batchFailures = computed(
  () =>
    batchReceipt.value?.results.filter((result) => result.state === 'failed') ??
    [],
)
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
async function collectSelected() {
  if (busy.value || !checked.value.length) return
  const ids = checked.value.map(String)
  busy.value = true
  batchReceipt.value = null
  try {
    const receipt = await props.service.collectBatch(ids)
    batchReceipt.value = receipt
    const succeeded = receipt.results.filter(
      (result) => result.state === 'demo',
    )
    const successIds = new Set(
      succeeded.flatMap((result) => result.candidateIds),
    )
    checked.value = checked.value.filter((key) => !successIds.has(String(key)))
    const feedback = `采集入库演示完成 ${succeeded.length} 项，失败 ${batchFailures.value.length} 项；未写入正式商品库`
    if (batchFailures.value.length) message.warning(feedback)
    else message.info(feedback)
  } catch (error) {
    message.error(
      error instanceof Error ? error.message : '批量演示失败，请重试',
    )
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
async function copyProductId(id: string) {
  try {
    await navigator.clipboard.writeText(id)
    message.success('商品ID已复制')
  } catch {
    message.error('商品ID复制失败')
  }
}
const missing = () => h(NText, { depth: 3 }, () => '—')
const columns = computed<DataTableColumns<SelectionCandidate>>(() => [
  { type: 'selection', width: 44, fixed: 'left', align: 'center' },
  {
    key: 'image',
    title: '图片',
    width: 104,
    fixed: 'left',
    align: 'center',
    render: (row) =>
      h(ExternalProductImage, { src: row.imageUrl, title: row.title }),
  },
  {
    key: 'shopName',
    title: '店铺名',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'title',
    title: '标题',
    width: 240,
    align: 'center',
    render: (row) => h(NEllipsis, { tooltip: true }, () => row.title),
  },
  {
    key: 'productId',
    title: '商品ID',
    width: 200,
    align: 'center',
    render: (row) =>
      h('div', { class: 'selection-product-id' }, [
        h(NEllipsis, { tooltip: true }, () => row.productId),
        h(
          AppButton,
          {
            tone: 'text',
            'aria-label': `复制商品ID ${row.productId}`,
            onClick: () => copyProductId(row.productId),
          },
          () => h(Copy, { size: 16, 'aria-hidden': true }),
        ),
      ]),
  },
  {
    key: 'category',
    title: '类目',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'priceBand',
    title: '价格带',
    width: 100,
    align: 'center',
    render: (row) => row.priceBand ?? missing(),
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
      row.listedAt ? formatCandidateDate(row.listedAt) : missing(),
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
        ? missing()
        : formatReviewRate(row.negativeReviewRate),
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
      <TableToolbar aria-label="候选商品批量操作">
        <NText :depth="3">已选择 {{ checked.length }} 项 · 全选仅当前页</NText>
        <template #actions>
          <AppButton
            :disabled="!checked.length || busy"
            :loading="busy"
            @click="collectSelected"
          >
            批量采集入库
          </AppButton>
        </template>
      </TableToolbar>
      <NAlert
        v-if="batchFailures.length"
        type="warning"
        title="演示采集失败"
        closable
        @close="batchReceipt = null"
      >
        <div v-for="result in batchFailures" :key="result.candidateId">
          {{ result.productId ?? result.candidateId }}：{{ result.message }}
        </div>
      </NAlert>
      <DataTable
        :columns="columns"
        :data="query.data.value?.items ?? []"
        :loading="query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="1408"
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

<style scoped>
:deep(.selection-product-id) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-width: 0;
}
</style>
