<script setup lang="ts">
import { computed, h, inject, ref, watch } from 'vue'
import { routeLocationKey, routerKey } from 'vue-router'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { useElementSize } from '@vueuse/core'
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
import { ProductInfoCell } from '@/entities/product'
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
  formatFirstListed,
  collectionLabels,
  discoveryLabels,
  discoveryDescriptions,
  rankChange,
  categoryLeaf,
} from '../model/candidate-display'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'
import { runResult } from '../model/run-display'
import { candidateFilters, candidateRoute } from '../model/candidate-query'
import { formatCandidateTime } from '../model/candidate-display'
import { basicFieldHint } from '../model/basic-display'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const emit = defineEmits<{ 'refresh-run-feedback': [] }>()
const message = useMessage()
const route = inject(routeLocationKey, null)
const router = inject(routerKey, null)
const filters = ref<CandidateQuery>(candidateFilters(route?.query ?? {}))
const keyword = ref(filters.value.keyword),
  checked = ref<DataTableRowKey[]>([]),
  detailId = ref<string | null>(null),
  busy = ref(false)
const selectionHint = ref<{ x: number; y: number } | null>(null)
const detailRunId = ref<string | null>(null)
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
const strategySearch = ref('')
const strategies = useQuery({
  queryKey: computed(() => [
    'selection-filter-strategies',
    props.contextKey,
    strategySearch.value,
  ]),
  queryFn: async () =>
    props.service.strategiesPage
      ? (
          await props.service.strategiesPage({
            page: 1,
            pageSize: 100,
            search: strategySearch.value,
          })
        ).items
      : props.service.strategies(),
  retry: false,
})
const selectedStrategy = useQuery({
  queryKey: computed(() => [
    'selection-filter-strategy',
    props.contextKey,
    filters.value.strategyId,
  ]),
  enabled: computed(
    () =>
      !!filters.value.strategyId &&
      !!props.service.strategy &&
      !strategies.data.value?.some(
        (row) => row.id === filters.value.strategyId,
      ),
  ),
  queryFn: ({ queryKey }) => props.service.strategy!(String(queryKey[2])),
  retry: false,
})
const strategyOptions = computed(() => {
  const options = (strategies.data.value ?? []).map((row) => ({
    label: row.name,
    value: row.id,
  }))
  if (
    selectedStrategy.data.value &&
    !options.some((option) => option.value === selectedStrategy.data.value!.id)
  )
    options.unshift({
      label: selectedStrategy.data.value.name,
      value: selectedStrategy.data.value.id,
    })
  return options
})
const batches = useQuery({
  queryKey: computed(() => [
    'selection-batches',
    props.contextKey,
    filters.value.strategyId,
    filters.value.shopId,
  ]),
  enabled: computed(
    () => !!filters.value.strategyId && !!props.service.batches,
  ),
  queryFn: ({ queryKey }) =>
    props.service.batches!(String(queryKey[2]), queryKey[3] as string | null),
  retry: false,
})
const batchOptions = computed(() => [
  { label: '最近执行', value: 'latest' },
  ...(batches.data.value ?? []).map((batch) => ({
    label: `${formatCandidateTime(batch.submitted_at)} · ${runResult(batch.execution)}${batch.detail_state === 'not_recorded' ? ' · 未记录明细' : batch.visible_item_count == null ? '' : ` · 可见 ${batch.visible_item_count} 项`}`,
    value: batch.receipt_id,
  })),
])
const queryReady = computed(
  () =>
    !filters.value.strategyId ||
    !props.service.batches ||
    !!filters.value.receiptId ||
    batches.isSuccess.value,
)
const resolvedFilters = computed<CandidateQuery>(() => ({
  ...filters.value,
  receiptId:
    filters.value.receiptId ??
    (filters.value.strategyId
      ? (batches.data.value?.[0]?.receipt_id ?? null)
      : null),
}))
const query = useQuery({
  queryKey: computed(() => [
    'selection-candidates',
    props.contextKey,
    { ...resolvedFilters.value },
  ]),
  queryFn: ({ queryKey }) =>
    props.service.candidates(queryKey[2] as CandidateQuery),
  enabled: queryReady,
  retry: false,
  placeholderData: keepPreviousData,
})
const latestRun = useQuery({
  queryKey: computed(() => [
    'selection-run',
    props.contextKey,
    filters.value.shopId,
  ]),
  enabled: computed(() => !!props.service.latestRun),
  queryFn: ({ queryKey }) =>
    props.service.latestRun!(queryKey[2] as string | null),
  retry: false,
  refetchInterval: (current) =>
    ['pending', 'running'].includes(current.state.data?.status ?? '')
      ? 1000
      : false,
})
watch(
  () => latestRun.data.value?.status,
  (status, old) => {
    if (
      status &&
      old &&
      ['pending', 'running'].includes(old) &&
      !['pending', 'running'].includes(status)
    )
      void query.refetch()
  },
)
const emptyDescription = computed(() => {
  const context = query.data.value?.context
  if (context?.detail_state === 'not_recorded')
    return '该历史批次未记录商品明细'
  if (context?.execution) return runResult(context.execution)
  if (props.service.available || filters.value.keyword) return '暂无候选商品'
  const run = latestRun.data.value
  if (!run) return '尚未获取候选，请在选品策略中执行手动选品'
  return ['failed', 'interrupted', 'pending', 'running'].includes(run.status)
    ? runResult(run)
    : '所选范围暂无候选商品'
})
async function refreshList() {
  emit('refresh-run-feedback')
  await Promise.all([
    query.refetch(),
    ...(props.service.latestRun ? [latestRun.refetch()] : []),
    ...(props.service.batches && filters.value.strategyId
      ? [batches.refetch()]
      : []),
  ])
}
const search = useAutoSearch(() => {
  filters.value = { ...filters.value, keyword: keyword.value.trim(), page: 1 }
  checked.value = []
})
function filterChanged() {
  search.cancel()
  filters.value.page = 1
  checked.value = []
}
watch(
  () => route?.query,
  (value) => {
    if (!value) return
    const restored = candidateFilters(value)
    if (JSON.stringify(restored) === JSON.stringify(filters.value)) return
    search.cancel()
    filters.value = restored
    keyword.value = restored.keyword
    checked.value = []
  },
)
watch(
  filters,
  (value) => {
    if (
      !router ||
      !route ||
      JSON.stringify(candidateFilters(route.query)) === JSON.stringify(value)
    )
      return
    void router.push({ query: { ...route.query, ...candidateRoute(value) } })
  },
  { deep: true },
)
function setStrategy(value: string | number | null) {
  filters.value.strategyId = value === null ? null : String(value)
  filters.value.receiptId = null
  filterChanged()
}
function setBatch(value: string | number | null) {
  filters.value.receiptId =
    value === null || value === 'latest' ? null : String(value)
  filterChanged()
}
function setBlocked(value: string | number | null) {
  filters.value.blocked = value === 'blocked'
  filterChanged()
}
function reset() {
  keyword.value = ''
  filters.value.shopId = null
  filters.value.blocked = false
  filters.value.resultScope = 'all'
  filters.value.strategyId = null
  filters.value.receiptId = null
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
  () => query.data.value,
  (result) => {
    const page = result?.page
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
    if (action !== 'collect' && props.service.blockCandidate) {
      await props.service.blockCandidate(row.id, action === 'block')
      message.success(action === 'block' ? '已屏蔽候选商品' : '已恢复候选商品')
      checked.value = []
      await query.refetch()
      return
    }
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
const basicCell = (
  row: SelectionCandidate,
  name: 'category_path' | 'first_on_shelf_date' | 'bad_comment_rate',
  content: ReturnType<typeof h> | string,
) =>
  h(
    NTooltip,
    { disabled: !row.basicInfoStatus && !row.basicInfoError },
    {
      trigger: () => content,
      default: () =>
        basicFieldHint(row.basicInfoStatus, name) || row.basicInfoError,
    },
  )
const wrappedHeader = (label: string) => () =>
  h('span', { style: { whiteSpace: 'normal' } }, label)
const tableRef = ref<InstanceType<typeof DataTable> | null>(null)
const { width: tableWidth } = useElementSize(() => {
  const element = tableRef.value?.$el
  return element instanceof HTMLElement ? element : null
})
const readingWidths = computed(() => {
  // Preserve the image and three actions; distribute the actual remaining
  // width, instead of forcing a captured 1496px table into every window.
  const width = Math.floor(tableWidth.value || 1496) - 2
  const space = Math.max(0, width - 44 - 220)
  const expand = Math.max(0, Math.min(1, (width - 1100) / 400))
  const fit = (compact: number, wide: number) =>
    Math.floor(compact + (wide - compact) * expand)
  const rank = fit(54, 88)
  const firstListed = 84
  const discovery = fit(66, 88)
  const price = fit(80, 112)
  const review = fit(84, 96)
  const listed = fit(106, 140)
  const status = fit(82, 100)
  const text = Math.max(
    0,
    space - rank - firstListed - discovery - price - review - listed - status,
  )
  // 48px image + 8px gap + ~260–280px text + 24px cell padding.
  // Cap the actual column as well as its text budget: the merchant column then
  // moves left on wide windows instead of leaving an empty identity column.
  const productInfo = Math.max(340, Math.min(360, text - 66 - 52))
  const remaining = Math.max(66 + 52, text - productInfo)
  const merchant = 66 + Math.floor((remaining - 66 - 52) * 0.6)
  const category = remaining - merchant
  return {
    productInfo,
    merchant,
    category,
    rank,
    firstListed,
    discovery,
    price,
    review,
    listed,
    status,
  }
})
const columns = computed<DataTableColumns<SelectionCandidate>>(() => [
  {
    type: 'selection',
    width: 44,
    fixed: 'left',
    align: 'center',
    className: 'selection-current-page',
  },
  {
    key: 'productInfo',
    title: wrappedHeader('商品信息'),
    width: readingWidths.value.productInfo,
    fixed: 'left',
    align: 'center',
    render: (row) =>
      h(ProductInfoCell, {
        imageUrl: row.imageUrl,
        title: row.title,
        productId: row.productId,
        density: 'compact',
      }),
  },
  {
    key: 'merchant',
    title: '店铺名',
    width: readingWidths.value.merchant,
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
    width: readingWidths.value.category,
    align: 'center',
    render: (row) => {
      const leaf = categoryLeaf(row.category)
      return basicCell(
        row,
        'category_path',
        leaf === '—'
          ? missing()
          : h(
              NEllipsis,
              { tooltip: true, style: { width: '100%', textAlign: 'center' } },
              () => leaf,
            ),
      )
    },
  },
  {
    key: 'rank',
    title: wrappedHeader('榜单排名'),
    width: readingWidths.value.rank,
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
    key: 'firstListed',
    title: wrappedHeader('首次上榜'),
    width: readingWidths.value.firstListed,
    align: 'center',
    render: (row) =>
      h(NText, { depth: row.firstListed === null ? 3 : 1 }, () =>
        formatFirstListed(row.firstListed),
      ),
  },
  {
    key: 'discovery',
    title: wrappedHeader('发现情况'),
    width: readingWidths.value.discovery,
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
    title: wrappedHeader('价格／价格带'),
    width: readingWidths.value.price,
    align: 'center',
    render: (row) =>
      row.priceBand === null
        ? missing()
        : h(
            NEllipsis,
            { tooltip: true, style: { width: '100%', textAlign: 'center' } },
            () => row.priceBand,
          ),
  },
  {
    key: 'negativeReviewRate',
    title: wrappedHeader('差评率'),
    width: readingWidths.value.review,
    className: 'selection-sort-column',
    align: 'center',
    sorter: props.service.available,
    sortOrder:
      filters.value.sortField === 'negativeReviewRate'
        ? filters.value.sortOrder
        : false,
    render: (row) =>
      basicCell(
        row,
        'bad_comment_rate',
        row.negativeReviewRate === null
          ? missing()
          : formatReviewRate(row.negativeReviewRate),
      ),
  },
  {
    key: 'listedAt',
    title: wrappedHeader('首次上架日期'),
    width: readingWidths.value.listed,
    className: 'selection-sort-column',
    align: 'center',
    sorter: true,
    sortOrder:
      filters.value.sortField === 'listedAt' ? filters.value.sortOrder : false,
    render: (row) =>
      basicCell(
        row,
        'first_on_shelf_date',
        row.listedAt ? formatCandidateDate(row.listedAt) : missing(),
      ),
  },
  {
    key: 'collectionStatus',
    title: '采集状态',
    width: readingWidths.value.status,
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
              detailRunId.value =
                row.resultRunId ?? filters.value.receiptId ?? null
            },
          },
          () => '详情',
        ),
        h(
          AppButton,
          {
            tone: 'secondary',
            size: 'small',
            disabled: busy.value || !props.service.available,
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
            disabled:
              busy.value ||
              !(
                props.service.candidateBlockAvailable ?? props.service.available
              ),
            onClick: () => act(row, row.blocked ? 'restore' : 'block'),
          },
          () => (row.blocked ? '恢复' : '屏蔽'),
        ),
      ]),
  },
])
const scrollWidth = computed(() => {
  const content = columns.value.reduce(
    (total, column) =>
      total + (typeof column.width === 'number' ? column.width : 0),
    0,
  )
  return tableWidth.value > 0 && content > tableWidth.value
    ? content
    : undefined
})
</script>

<template>
  <div
    class="selection-panel candidate-pool"
    @mouseover="showSelectionHint"
    @focusin="showSelectionHint"
    @mouseleave="selectionHint = null"
    @focusout="selectionHint = null"
  >
    <FilterBar density="compact">
      <FilterField width="md"
        ><ShopSelector
          v-model="filters.shopId"
          clearable
          label-tooltip
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
          :disabled="!(service.candidateBlockAvailable ?? service.available)"
          aria-label="屏蔽状态筛选"
          :model-value="filters.blocked ? 'blocked' : 'normal'"
          :options="[
            { label: '未屏蔽', value: 'normal' },
            { label: '已屏蔽', value: 'blocked' },
          ]"
          @update:model-value="setBlocked"
      /></FilterField>
      <FilterField width="sm"
        ><AppSelect
          v-model="filters.resultScope"
          aria-label="结果范围"
          :options="[
            { label: '全部结果', value: 'all' },
            { label: '今日结果', value: 'today' },
            { label: '今日新发现', value: 'today_new' },
            { label: '今日已发现', value: 'today_known' },
          ]"
          @update:model-value="filterChanged"
      /></FilterField>
      <FilterField width="md"
        ><AppSelect
          :model-value="filters.strategyId"
          placeholder="全部策略"
          aria-label="选品策略筛选"
          label-tooltip
          clearable
          filterable
          remote
          :loading="strategies.isPending.value"
          :options="strategyOptions"
          @search="strategySearch = $event"
          @update:model-value="setStrategy"
      /></FilterField>
      <FilterField v-if="filters.strategyId" width="md"
        ><AppSelect
          :model-value="filters.receiptId ?? 'latest'"
          :options="batchOptions"
          aria-label="执行批次"
          label-tooltip
          :loading="batches.isPending.value"
          @update:model-value="setBatch"
      /></FilterField>
      <template #actions
        ><AppButton @click="reset">重置</AppButton
        ><AppButton tone="secondary" @click="refreshList"
          >刷新列表</AppButton
        ></template
      >
    </FilterBar>
    <ManagementListSection density="compact">
      <NAlert
        v-if="
          strategies.isError.value ||
          selectedStrategy.isError.value ||
          batches.isError.value
        "
        type="error"
        >{{
          strategies.error.value?.message ??
          selectedStrategy.error.value?.message ??
          batches.error.value?.message
        }}</NAlert
      >
      <NAlert v-if="latestRun.isError.value" type="warning">{{
        latestRun.error.value?.message
      }}</NAlert>
      <TableToolbar density="compact" aria-label="候选商品批量操作">
        <NText v-if="checked.length" :depth="3"
          >已选 {{ checked.length }} 项</NText
        >
        <NText
          v-if="query.data.value?.context?.unknown_discovery_count"
          depth="3"
          >{{
            query.data.value.context.unknown_discovery_count
          }}
          项发现状态未知</NText
        >
        <template #actions>
          <AppButton
            tone="primary"
            :disabled="!checked.length || busy || !service.available"
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
        ref="tableRef"
        :columns="columns"
        :data="query.data.value?.items ?? []"
        :loading="queryReady && query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="scrollWidth"
        viewport="fill"
        appearance="list"
        :checked-row-keys="checked"
        :empty-description="emptyDescription"
        @update:checked-row-keys="checked = $event"
        @retry="query.refetch()"
        @update:sorter="sort"
      />
      <PaginationBar
        density="compact"
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
      :receipt-id="detailRunId"
      :service="service"
      :context-key="contextKey"
      @close="detailId = null"
      @updated="query.refetch()"
    />
  </div>
</template>

<style scoped>
.candidate-pool :deep(.n-data-table .selection-current-page) {
  padding: var(--n-td-padding);
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
