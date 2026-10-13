<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { PageResult } from '@/shared/api'
import {
  useMessage,
  type DataTableColumns,
  NText,
  NAlert,
  NTooltip,
} from 'naive-ui'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
  StatusTag,
  ErrorState,
} from '@/shared/components'
import { AppButton, AppInput, AppSwitch } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import {
  CHANNEL_OPTIONS,
  type SelectionService,
  type SelectionStrategy,
  type SelectionExecutionSummary,
} from '../model/contracts'
import { conditionSummary } from '../model/selection-rules'
import StrategyDrawer from './StrategyDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const emit = defineEmits<{
  submitted: [execution: SelectionExecutionSummary]
  'refresh-run-feedback': []
}>()
const message = useMessage()
const page = ref(1),
  pageSize = ref(20),
  keyword = ref(''),
  appliedKeyword = ref('')
const editing = ref<SelectionStrategy | null>(null),
  drawer = ref(false)
const busyId = ref<string | null>(null)
const queryClient = useQueryClient()
let mounted = true
onBeforeUnmount(() => {
  mounted = false
})
const canRead = computed(
  () => props.service.strategySaveAvailable ?? props.service.available,
)
const listKey = computed(() => [
  'selection-strategies',
  props.contextKey,
  props.service.strategiesPage ? page.value : null,
  props.service.strategiesPage ? pageSize.value : null,
  props.service.strategiesPage ? appliedKeyword.value : null,
])
const query = useQuery({
  queryKey: listKey,
  enabled: canRead,
  queryFn: async () =>
    props.service.strategiesPage
      ? props.service.strategiesPage({
          page: page.value,
          pageSize: pageSize.value,
          search: appliedKeyword.value,
        })
      : { items: await props.service.strategies(), total: 0 },
  refetchInterval: (query) =>
    query.state.data?.items.some((row) =>
      ['pending', 'running'].includes(row.latestExecution?.status ?? ''),
    )
      ? 2000
      : false,
  retry: false,
})
// Keep the approved management and drawer independent of manual availability.
// Capabilities govern formal writes/execution, not whether a draft can be viewed.
const capability = useQuery({
  queryKey: computed(() => ['selection-capabilities', props.contextKey]),
  enabled: computed(() => !!props.service.manual),
  queryFn: () => props.service.manual!.capabilities(),
  retry: false,
})
const canSave = computed(
  () => capability.data.value?.strategy_save_available ?? canRead.value,
)
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
  emit('refresh-run-feedback')
  if (canRead.value) void query.refetch()
  if (props.service.manual) {
    void capability.refetch()
    void latest.refetch()
  }
}
function retrieved(execution?: SelectionExecutionSummary) {
  if (execution) {
    emit('submitted', execution)
  }
  if (canRead.value) void query.refetch()
  if (props.service.manual) void latest.refetch()
}
const filtered = computed(() =>
  (query.data.value?.items ?? []).filter((row) =>
    row.name
      .toLocaleLowerCase()
      .includes(appliedKeyword.value.toLocaleLowerCase()),
  ),
)
const rows = computed(() =>
  props.service.strategiesPage
    ? (query.data.value?.items ?? [])
    : filtered.value.slice(
        (page.value - 1) * pageSize.value,
        page.value * pageSize.value,
      ),
)
const total = computed(() =>
  props.service.strategiesPage
    ? (query.data.value?.total ?? 0)
    : filtered.value.length,
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
function updateSavedRow(row: SelectionStrategy) {
  // Update the existing Query page in place; never build a second row store or
  // move it to the front. The subsequent authorized GET remains authoritative.
  queryClient.setQueryData<PageResult<SelectionStrategy>>(
    listKey.value,
    (previous) =>
      previous
        ? {
            ...previous,
            items: previous.items.map((item) =>
              item.id === row.id &&
              !(item.version && row.version && item.version > row.version)
                ? row
                : item,
            ),
          }
        : previous,
  )
}
async function saved(row?: SelectionStrategy) {
  if (!mounted) return
  if (editing.value) {
    if (row) updateSavedRow(row)
  } else {
    setPage(1)
    await nextTick()
  }
  if (!mounted) return
  void query.refetch()
}
async function retrieve(row: SelectionStrategy) {
  if (busyId.value) return
  busyId.value = row.id
  try {
    if (props.service.manual) {
      if (executionDisabledReason.value)
        throw new Error(executionDisabledReason.value)
      if (!row.version) throw new Error('请刷新已保存的策略版本')
      const encoded = JSON.stringify({
        id: row.id,
        version: row.version,
        shop: row.shopId,
        channels: row.channels,
      })
      if (uncertainSubmission?.input !== encoded)
        uncertainSubmission = { input: encoded, key: crypto.randomUUID() }
      const receipt = await props.service.manual.submit(
        row,
        uncertainSubmission.key,
        undefined,
        { id: row.id, version: row.version },
      )
      uncertainSubmission = null
      message.info(receipt.reused ? '已复用选品任务' : '已提交选品任务')
      retrieved(receipt.execution)
    } else {
      const receipt = await props.service.retrieve(row, row.id)
      message.info(receipt.message)
    }
    await query.refetch()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '获取失败')
  } finally {
    busyId.value = null
  }
}
let uncertainSubmission: { input: string; key: string } | null = null
async function toggle(row: SelectionStrategy, enabled: boolean) {
  if (!props.service.toggleStrategy || !canSave.value || busyId.value) return
  busyId.value = row.id
  const context = props.contextKey
  try {
    const saved = await props.service.toggleStrategy(row, enabled)
    if (!mounted || props.contextKey !== context) return
    updateSavedRow(saved)
    message.success(enabled ? '策略已启用' : '策略已停用')
    await query.refetch()
  } catch (error) {
    if (mounted && props.contextKey === context)
      message.error(error instanceof Error ? error.message : '状态修改失败')
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
        : h(
            NTooltip,
            {},
            {
              trigger: () =>
                `${row.scheduleKind === 'hourly' ? '每小时' : `每日 ${row.dailyTime}`}${row.scheduleAvailable === false ? ' · 未调度' : ''}`,
              default: () =>
                row.scheduleAvailable === false
                  ? '定时配置已保存，服务端调度待接入'
                  : 'Asia/Shanghai',
            },
          ),
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
      props.service.toggleStrategy
        ? h(AppSwitch, {
            modelValue: row.enabled,
            disabled: !!busyId.value || !canSave.value,
            'aria-label': `${row.name}启用状态`,
            'onUpdate:modelValue': (enabled: boolean) => toggle(row, enabled),
          })
        : h(StatusTag, {
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
            disabled:
              !!props.service.manual &&
              (!!executionDisabledReason.value ||
                ['pending', 'running'].includes(
                  row.latestExecution?.status ?? '',
                )),
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
        ><AppButton
          tone="primary"
          :disabled="capability.data.value?.strategy_save_available === false"
          @click="edit(null)"
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
      </template>
      <DataTable
        :columns="columns"
        :data="rows"
        :loading="canRead && query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="1510"
        viewport="fill"
        appearance="list"
        :empty-description="
          canRead ? '暂无选品策略' : '策略保存与定时执行待接入'
        "
        @retry="query.refetch()"
      />
      <PaginationBar
        :page="page"
        :page-size="pageSize"
        :item-count="total"
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
      :capabilities="capability.data.value"
      @saved="saved"
      @retrieved="retrieved"
    />
  </div>
</template>
