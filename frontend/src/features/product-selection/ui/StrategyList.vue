<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  useMessage,
  type DataTableColumns,
  type DataTableRowKey,
} from 'naive-ui'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
  StatusTag,
} from '@/shared/components'
import { AppButton, AppInput } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import {
  CHANNEL_OPTIONS,
  type SelectionService,
  type SelectionStrategy,
} from '../model/contracts'
import { conditionSummary } from '../model/selection-rules'
import StrategyDrawer from './StrategyDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const message = useMessage()
const page = ref(1),
  pageSize = ref(20),
  keyword = ref(''),
  appliedKeyword = ref('')
const checked = ref<DataTableRowKey[]>([])
const editing = ref<SelectionStrategy | null>(null),
  drawer = ref(false)
const busyId = ref<string | null>(null)
const query = useQuery({
  queryKey: computed(() => ['selection-strategies', props.contextKey]),
  queryFn: () => props.service.strategies(),
  retry: false,
})
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
  checked.value = []
})
function edit(row: SelectionStrategy | null) {
  editing.value = row
  drawer.value = true
}
function setPage(value: number) {
  page.value = value
  checked.value = []
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
  { type: 'selection', fixed: 'left', width: 44, align: 'center' },
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
      CHANNEL_OPTIONS.find((option) => option.value === row.channel)!.label,
  },
  {
    key: 'conditions',
    title: '条件摘要',
    width: 230,
    align: 'center',
    ellipsis: { tooltip: true },
    render: conditionSummary,
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
          ? '每小时（演示）'
          : `每日 ${row.dailyTime}（演示）`,
  },
  {
    key: 'latestResult',
    title: '最近结果',
    width: 150,
    align: 'center',
    render: (row) => row.latestResult ?? '—',
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
            tone: 'text',
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
        ><AppButton @click="query.refetch()">刷新</AppButton
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
      <DataTable
        :columns="columns"
        :data="rows"
        :loading="query.isPending.value"
        :error="query.error.value?.message"
        :row-key="(row) => row.id"
        :scroll-x="1554"
        viewport="fill"
        appearance="list"
        :checked-row-keys="checked"
        empty-description="暂无选品策略"
        @update:checked-row-keys="checked = $event"
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
      @saved="saved"
    />
  </div>
</template>
