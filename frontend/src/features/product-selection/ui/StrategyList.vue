<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useMessage, type DataTableColumns, NText, NAlert } from 'naive-ui'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
  StatusTag,
  ErrorState,
} from '@/shared/components'
import { AppButton, AppInput } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import {
  CHANNEL_OPTIONS,
  type SelectionService,
  type SelectionStrategy,
} from '../model/contracts'
import { conditionSummary } from '../model/selection-rules'
import { runWindow, runResult } from '../model/run-display'
import StrategyDrawer from './StrategyDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const message = useMessage()
const page = ref(1),
  pageSize = ref(20),
  keyword = ref(''),
  appliedKeyword = ref('')
const editing = ref<SelectionStrategy | null>(null),
  drawer = ref(false)
const busyId = ref<string | null>(null)
const query = useQuery({
  queryKey: computed(() => ['selection-strategies', props.contextKey]),
  enabled: computed(() => props.service.available),
  queryFn: () => props.service.strategies(),
  retry: false,
})
// Preserve strategy management even while its persistence/scheduler is not
// connected. Only formal run reads and explicit manual submission are available.
const capability = useQuery({
  queryKey: computed(() => ['selection-capabilities', props.contextKey]),
  enabled: computed(() => !!props.service.manual),
  queryFn: () => props.service.manual!.capabilities(),
  retry: false,
})
const latest = useQuery({
  queryKey: computed(() => ['selection-manual-run', props.contextKey]),
  enabled: computed(() => !!props.service.manual),
  queryFn: () => props.service.latestRun!(null),
  retry: false,
  refetchInterval: (query) =>
    ['pending', 'running'].includes(query.state.data?.status ?? '')
      ? 2000
      : false,
})
const executionDisabledReason = computed(() => {
  if (!props.service.manual) return null
  if (capability.isPending.value) return '正在读取手动获取状态'
  if (capability.isError.value) return '手动获取状态读取失败，请刷新重试'
  if (!capability.data.value?.manual_execution_available)
    return '此环境手动获取未启用，已入库结果仍可查询'
  if (['pending', 'running'].includes(latest.data.value?.status ?? ''))
    return '已有选品获取任务正在执行'
  return null
})
function refresh() {
  if (props.service.available) void query.refetch()
  if (props.service.manual) {
    void capability.refetch()
    void latest.refetch()
  }
}
function retrieved() {
  if (props.service.available) void query.refetch()
  if (props.service.manual) void latest.refetch()
}
const filtered = computed(() =>
  (query.data.value ?? []).filter((row) =>
    row.name
      .toLocaleLowerCase()
      .includes(appliedKeyword.value.toLocaleLowerCase()),
  ),
)
const rows = computed(() =>
  filtered.value.slice(
    (page.value - 1) * pageSize.value,
    page.value * pageSize.value,
  ),
)
const search = useAutoSearch(() => {
  appliedKeyword.value = keyword.value.trim()
  page.value = 1
})
function edit(row: SelectionStrategy | null) {
  editing.value = row
  drawer.value = true
}
function setPage(value: number) {
  page.value = value
}
function setPageSize(value: number) {
  pageSize.value = value
  setPage(1)
}
function saved() {
  void query.refetch()
  setPage(1)
}
async function retrieve(row: SelectionStrategy) {
  if (busyId.value) return
  busyId.value = row.id
  try {
    const receipt = await props.service.retrieve(row, row.id)
    message.info(receipt.message)
    await query.refetch()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '获取失败')
  } finally {
    busyId.value = null
  }
}
const columns = computed<DataTableColumns<SelectionStrategy>>(() => [
  {
    key: 'name',
    title: '策略名',
    width: 180,
    fixed: 'left',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    key: 'shopName',
    title: '请求店铺',
    width: 170,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  { key: 'creatorName', title: '达人账号', width: 130, align: 'center' },
  {
    key: 'channel',
    title: '渠道',
    width: 130,
    align: 'center',
    render: (row) =>
      CHANNEL_OPTIONS.filter((option) =>
        option.value === 'short-video'
          ? row.channels.shortVideo.selected
          : row.channels.baiying.selected,
      )
        .map((option) => option.label)
        .join('、'),
  },
  {
    key: 'conditions',
    title: '条件摘要',
    width: 230,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) =>
      conditionSummary(row) === '—'
        ? h(NText, { depth: 3 }, () => '—')
        : conditionSummary(row),
  },
  {
    key: 'execution',
    title: '执行方式',
    width: 150,
    align: 'center',
    render: (row) =>
      !row.scheduled
        ? '手动'
        : row.scheduleKind === 'hourly'
          ? '每小时'
          : `每日 ${row.dailyTime}`,
  },
  {
    key: 'latestResult',
    title: '最近结果',
    width: 150,
    align: 'center',
    render: (row) =>
      row.latestResult
        ? h(NText, { depth: 2 }, () => row.latestResult)
        : h(NText, { depth: 3 }, () => '—'),
  },
  {
    key: 'enabled',
    title: '状态',
    width: 90,
    align: 'center',
    render: (row) =>
      h(StatusTag, {
        label: row.enabled ? '启用' : '停用',
        tone: row.enabled ? 'success' : 'neutral',
      }),
  },
  {
    key: 'actions',
    title: '操作',
    width: 180,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h('div', { class: 'selection-row-actions' }, [
        h(
          AppButton,
          {
            tone: 'primary',
            loading: busyId.value === row.id,
            onClick: () => retrieve(row),
          },
          () => '立即获取',
        ),
        h(AppButton, { tone: 'text', onClick: () => edit(row) }, () => '编辑'),
      ]),
  },
])
</script>

<template>
  <div class="selection-panel">
    <FilterBar>
      <FilterField width="lg"
        ><AppInput
          v-model="keyword"
          aria-label="搜索策略名称"
          placeholder="搜索策略名称"
          clearable
          @update:model-value="search.onInput"
          @compositionstart="search.onCompositionStart"
          @compositionend="search.onCompositionEnd(keyword)"
          @keydown.enter="search.onEnter"
      /></FilterField>
      <template #actions
        ><AppButton @click="refresh">刷新</AppButton
        ><AppButton @click="message.info('达人登录尚未接入')"
          >达人登录</AppButton
        ></template
      >
      <template #primary-action
        ><AppButton tone="primary" @click="edit(null)"
          >新建策略</AppButton
        ></template
      >
    </FilterBar>
    <ManagementListSection>
      <template v-if="service.manual">
        <ErrorState
          v-if="capability.isError.value"
          description="手动获取状态读取失败"
          retryable
          @retry="capability.refetch()"
        />
        <NAlert
          v-else-if="
            !capability.isPending.value &&
            !capability.data.value?.manual_execution_available
          "
          type="warning"
          >此环境手动获取未启用，已入库结果仍可查询</NAlert
        >
        <ErrorState
          v-if="latest.isError.value"
          description="获取进度查询失败"
          retryable
          @retry="latest.refetch()"
        />
        <NAlert
          v-else-if="latest.data.value"
          :type="
            ['failed', 'interrupted'].includes(latest.data.value.status)
              ? 'error'
              : latest.data.value.status === 'partial'
                ? 'warning'
                : 'info'
          "
          >最近获取：{{ runResult(latest.data.value) }} ·
          {{ runWindow(latest.data.value) }}</NAlert
        >
      </template>
      <DataTable
        :columns="columns"
        :data="rows"
        :loading="service.available && query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="1510"
        viewport="fill"
        appearance="list"
        :empty-description="
          service.available ? '暂无选品策略' : '策略保存与定时执行待接入'
        "
        @retry="query.refetch()"
      />
      <PaginationBar
        :page="page"
        :page-size="pageSize"
        :item-count="filtered.length"
        @update:page="setPage"
        @update:page-size="setPageSize"
      />
    </ManagementListSection>
    <StrategyDrawer
      v-model:show="drawer"
      :strategy="editing"
      :service="service"
      :context-key="contextKey"
      :execution-disabled-reason="executionDisabledReason"
      @saved="saved"
      @retrieved="retrieved"
    />
  </div>
</template>
