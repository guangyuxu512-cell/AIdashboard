<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import {
  type DataTableColumns,
  type DataTableRowKey,
  type DataTableSortState,
  NText,
  NEllipsis,
  NAlert,
  NTooltip,
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
  StatusTag,
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
  collectionLabels,
  discoveryLabels,
  discoveryDescriptions,
  rankChange,
  categoryLeaf,
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
const selectionHint = ref<{ x: number; y: number } | null>(null)
function showSelectionHint(event: Event) {
  const checkbox =
    event.target instanceof Element
      ? event.target.closest('th.selection-current-page [role="checkbox"]')
      : null
  if (!checkbox) {
    selectionHint.value = null
    return
  }
  const bounds = checkbox.getBoundingClientRect()
  selectionHint.value = {
    x: bounds.left + bounds.width / 2,
    y: bounds.bottom,
  }
}
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
    const feedback = `资料采集演示完成 ${succeeded.length} 项，失败 ${batchFailures.value.length} 项；未发起真实采集`
    if (batchFailures.value.length) message.warning(feedback)
    else message.info(feedback)
    await query.refetch()
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
const missing = () => h(NText, { depth: 3 }, () => '—')
const columns = computed<DataTableColumns<SelectionCandidate>>(() => [
  {
    type: 'selection',
    width: 44,
    fixed: 'left',
    align: 'center',
    className: 'selection-current-page',
  },
  {
    key: 'image',
    title: '缩略图',
    width: 80,
    fixed: 'left',
    align: 'center',
    render: (row) =>
      h(ExternalProductImage, {
        src: row.imageUrl,
        title: row.title,
        size: 'thumbnail',
      }),
  },
  {
    key: 'title',
    title: '商品标题',
    minWidth: 240,
    align: 'center',
    render: (row) =>
      h(
        NEllipsis,
        {
          lineClamp: 2,
          tooltip: true,
          style: { width: '100%', textAlign: 'center' },
        },
        () => row.title,
      ),
  },
  {
    key: 'merchant',
    title: '店铺名',
    width: 150,
    align: 'center',
    render: (row) =>
      row.merchant
        ? h(
            NEllipsis,
            { tooltip: true, style: { width: '100%', textAlign: 'center' } },
            () => row.merchant!.name,
          )
        : missing(),
  },
  {
    key: 'category',
    title: '类目',
    width: 120,
    align: 'center',
    render: (row) => {
      const leaf = categoryLeaf(row.category)
      return leaf === '—'
        ? missing()
        : h(
            NEllipsis,
            { tooltip: true, style: { width: '100%', textAlign: 'center' } },
            () => leaf,
          )
    },
  },
  {
    key: 'rank',
    title: '榜单排名',
    width: 100,
    align: 'center',
    render: (row) => {
      const change = rankChange(row)
      return h('div', [
        row.rank ?? missing(),
        change
          ? h(
              NText,
              { type: change.type, tag: 'div', depth: 1 },
              () => change.label,
            )
          : null,
      ])
    },
  },
  {
    key: 'discovery',
    title: '发现情况',
    width: 100,
    align: 'center',
    render: (row) =>
      h(
        NTooltip,
        {},
        {
          trigger: () =>
            h(
              NText,
              { depth: row.discovery === 'unknown' ? 3 : 1 },
              () => discoveryLabels[row.discovery],
            ),
          default: () => discoveryDescriptions[row.discovery],
        },
      ),
  },
  {
    key: 'priceBand',
    title: '价格／价格带',
    width: 120,
    align: 'center',
    render: (row) => row.priceBand ?? missing(),
  },
  {
    key: 'negativeReviewRate',
    title: '差评率',
    width: 100,
    className: 'selection-sort-column',
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
    key: 'listedAt',
    title: '首次上架日期',
    width: 140,
    className: 'selection-sort-column',
    align: 'center',
    sorter: true,
    sortOrder:
      filters.value.sortField === 'listedAt' ? filters.value.sortOrder : false,
    render: (row) =>
      row.listedAt ? formatCandidateDate(row.listedAt) : missing(),
  },
  {
    key: 'collectionStatus',
    title: '采集状态',
    width: 120,
    align: 'center',
    render: (row) =>
      row.collectionStatus === 'unknown'
        ? missing()
        : h(StatusTag, {
            label: collectionLabels[row.collectionStatus],
            tone: row.collectionStatus === 'failed' ? 'error' : 'neutral',
          }),
  },
  {
    key: 'actions',
    title: '操作',
    width: 220,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h('div', { class: 'selection-row-actions selection-candidate-actions' }, [
        h(
          AppButton,
          {
            tone: 'link',
            size: 'small',
            onClick: () => {
              detailId.value = row.id
            },
          },
          () => '详情',
        ),
        h(
          AppButton,
          {
            tone: 'secondary',
            size: 'small',
            disabled: busy.value,
            onClick: () => act(row, 'collect'),
          },
          () => '采集资料',
        ),
        h(
          AppButton,
          {
            tone: 'text',
            size: 'small',
            themeOverrides: { paddingSmall: '0' },
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
  <div
    class="selection-panel candidate-pool"
    @mouseover="showSelectionHint"
    @focusin="showSelectionHint"
    @mouseleave="selectionHint = null"
    @focusout="selectionHint = null"
  >
    <FilterBar>
      <FilterField width="md"
        ><ShopSelector
          v-model="filters.shopId"
          placeholder="全部请求店铺"
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
        ><AppButton tone="secondary" @click="query.refetch()"
          >刷新列表</AppButton
        ></template
      >
    </FilterBar>
    <ManagementListSection>
      <TableToolbar aria-label="候选商品批量操作">
        <NText v-if="checked.length" :depth="3"
          >已选 {{ checked.length }} 项</NText
        >
        <template #actions>
          <AppButton
            tone="primary"
            :disabled="!checked.length || busy"
            :loading="busy"
            @click="collectSelected"
          >
            批量采集资料
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
        :scroll-x="1534"
        :theme-overrides="{
          tdPaddingMedium: 'var(--space-3)',
          thPaddingMedium: 'var(--space-3)',
        }"
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
    <NTooltip
      v-if="selectionHint"
      trigger="manual"
      placement="bottom"
      :show="true"
      :x="selectionHint.x"
      :y="selectionHint.y"
      >全选仅当前页</NTooltip
    >
    <CandidateDetailDrawer
      :id="detailId"
      :service="service"
      :context-key="contextKey"
      @close="detailId = null"
      @updated="query.refetch()"
    />
  </div>
</template>

<style scoped>
.candidate-pool :deep(.n-data-table .selection-current-page) {
  padding: var(--space-3);
}
.candidate-pool :deep(.selection-sort-column .n-data-table-th__title-wrapper) {
  justify-content: center;
}
.candidate-pool :deep(.selection-sort-column .n-data-table-th__title) {
  flex: 0 1 auto;
}
.candidate-pool :deep(.selection-candidate-actions) {
  justify-content: center;
  gap: var(--space-3);
  flex-wrap: nowrap;
}
</style>
