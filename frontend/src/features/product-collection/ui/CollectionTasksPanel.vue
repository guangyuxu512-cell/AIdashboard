<script setup lang="ts">
import { computed, h, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NEllipsis,
  NText,
  NTooltip,
  type DataTableColumns,
  type DataTableRowKey,
} from 'naive-ui'
import { useMessage } from 'naive-ui'
import {
  getPlatformDefinition,
  type PlatformCode,
} from '@/entities/platform/model/registry'
import { PlatformDisplay, PlatformIcon } from '@/entities/platform'
import { apiMode } from '@/shared/api'
import {
  ContextSwitchBar,
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  FilterField,
  LoadingState,
  ManagementListSection,
  PageSection,
  PaginationBar,
  StatusTag,
  TableToolbar,
} from '@/shared/components'
import { AppButton, AppInput, AppRadio, AppSelect } from '@/shared/ui'
import {
  COLLECTION_TASKS_UNAVAILABLE,
  createCollectionTaskService,
} from '../api/collection-task-service'
import type {
  CollectionInputMode,
  CollectionTask,
  CollectionTaskPage,
  CollectionTaskService,
  CollectionTaskStatus,
} from '../model/contracts'
import CollectionTaskDetailDialog from './CollectionTaskDetailDialog.vue'

const props = defineProps<{ contextKey: string }>()
const router = useRouter()
const message = useMessage()
const service = shallowRef<CollectionTaskService | null>(null)
const loadError = ref<string | null>(null)
const listError = ref<string | null>(null)
const loading = ref(false)
const busy = ref(false)
const pageData = ref<CollectionTaskPage | null>(null)
const selected = ref<DataTableRowKey[]>([])
const detail = ref<CollectionTask | null>(null)
const platform = ref<PlatformCode>('douyin')
const inputMode = ref<CollectionInputMode>('product')
const draft = ref('')
const keyword = ref('')
const filterPlatform = ref<PlatformCode | null>(null)
const status = ref<CollectionTaskStatus | null>(null)
const page = ref(1)
const pageSize = ref(20)
let revision = 0

const platformItems = (['douyin', 'pdd', 'taobao'] as PlatformCode[]).map(
  (code) => ({ key: code, label: getPlatformDefinition(code)?.label ?? code }),
)
const platformOptions = [
  { label: '全部平台', value: 'all' },
  ...platformItems.map((item) => ({ label: item.label, value: item.key })),
]
const inputModeOptions = [
  { label: '商品 ID／链接', value: 'product' },
  { label: '店铺口令', value: 'shop-code' },
]
const statusLabels: Record<CollectionTaskStatus, string> = {
  queued: '排队中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}
const statusTones = {
  queued: 'neutral',
  processing: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'neutral',
} as const
const statusItems = computed(() => {
  const counts = pageData.value?.counts
  return [
    { key: 'all', label: `全部 ${counts?.all ?? 0}` },
    ...(
      ['queued', 'processing', 'completed', 'failed', 'cancelled'] as const
    ).map((key) => ({
      key,
      label: `${statusLabels[key]} ${counts?.[key] ?? 0}`,
    })),
  ]
})

async function loadService() {
  const current = ++revision
  service.value = null
  loadError.value = null
  try {
    const resolved = await createCollectionTaskService(apiMode)
    if (current === revision) service.value = resolved
  } catch (error) {
    if (current === revision)
      loadError.value = error instanceof Error ? error.message : '加载失败'
  }
}

async function fetchList() {
  if (!service.value?.available) return
  loading.value = true
  listError.value = null
  try {
    const result = await service.value.list({
      keyword: keyword.value.trim(),
      platform: filterPlatform.value,
      status: status.value,
      page: page.value,
      pageSize: pageSize.value,
    })
    pageData.value = result
    page.value = result.page
    selected.value = []
  } catch (error) {
    listError.value =
      error instanceof Error ? error.message : '任务列表加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.contextKey,
  async () => {
    await loadService()
    await fetchList()
  },
  { immediate: true },
)
watch([status, filterPlatform, page, pageSize], fetchList)

function setPlatform(key: string) {
  platform.value = key as PlatformCode
  inputMode.value = 'product'
}

function setStatus(key: string) {
  status.value = key === 'all' ? null : (key as CollectionTaskStatus)
  page.value = 1
}

function searchTasks() {
  page.value = 1
  void fetchList()
}

function setFilterPlatform(value: string | number | null) {
  filterPlatform.value =
    value === 'all' || value === null ? null : (value as PlatformCode)
  page.value = 1
}

function setTaskPageSize(value: number) {
  pageSize.value = value
  page.value = 1
}

function parsedValues(): string[] {
  return draft.value
    .split(/\r?\n|[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function validate(values: string[]): string | null {
  if (!values.length) return '请输入至少一个商品 ID、链接或店铺口令'
  if (new Set(values).size !== values.length)
    return '输入中存在重复项，请检查后再创建'
  if (inputMode.value === 'shop-code') return null
  const invalid = values.find(
    (value) => !/^\d{8,}$/.test(value) && !/^https?:\/\/\S+$/i.test(value),
  )
  return invalid ? `无法识别：${invalid}` : null
}

async function createTasks() {
  if (!service.value?.available || busy.value) return
  const values = parsedValues()
  const error = validate(values)
  if (error) {
    message.error(error)
    return
  }
  busy.value = true
  try {
    const result = await service.value.create({
      platform: platform.value,
      inputMode: inputMode.value,
      values,
    })
    if (result.created.length)
      message.info(
        `已演示创建 ${result.created.length} 个采集任务；未向手机派发`,
      )
    if (result.duplicates.length)
      message.warning(`已跳过 ${result.duplicates.length} 个重复任务`)
    if (result.created.length) draft.value = ''
    page.value = 1
    await fetchList()
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '创建失败')
  } finally {
    busy.value = false
  }
}

async function retry(ids: string[]) {
  if (!service.value?.available || busy.value) return
  busy.value = true
  try {
    const count = await service.value.retry(ids)
    message.info(count ? `已演示重试 ${count} 个任务` : '没有可重试的任务')
    await fetchList()
  } finally {
    busy.value = false
  }
}

async function cancel(ids: string[]) {
  if (!service.value?.available || busy.value) return
  busy.value = true
  try {
    const count = await service.value.cancel(ids)
    message.info(count ? `已演示取消 ${count} 个任务` : '没有可取消的任务')
    await fetchList()
  } finally {
    busy.value = false
  }
}

function viewProduct(row: CollectionTask) {
  void router.push({ path: '/products', query: { productId: row.productId } })
}

const columns = computed<DataTableColumns<CollectionTask>>(() => [
  { type: 'selection', width: 44, fixed: 'left' },
  {
    title: '平台',
    key: 'platform',
    width: 112,
    align: 'center',
    render: (row) => h(PlatformDisplay, { code: row.platform }),
  },
  {
    title: '商品／提交内容',
    key: 'target',
    width: 280,
    ellipsis: { tooltip: true },
    render: (row) =>
      h(NEllipsis, { tooltip: true, lineClamp: 1 }, () =>
        row.title
          ? `${row.title} · ${row.productId ?? row.inputValue}`
          : row.inputValue,
      ),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    align: 'center',
    render: (row) =>
      h(StatusTag, {
        label: statusLabels[row.status],
        tone: statusTones[row.status],
      }),
  },
  {
    title: '进度',
    key: 'progress',
    width: 96,
    align: 'center',
    render: (row) => (row.progress === null ? '—' : `${row.progress}%`),
  },
  {
    title: '更新时间',
    key: 'updatedAt',
    width: 176,
    align: 'center',
    render: (row) => row.updatedAt.replace('T', ' ').slice(0, 16),
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h('div', { class: 'collection-task-actions' }, [
        h(
          AppButton,
          { tone: 'link', size: 'small', onClick: () => (detail.value = row) },
          () => '详情',
        ),
        row.status === 'completed' && row.productId
          ? h(
              AppButton,
              { size: 'small', onClick: () => viewProduct(row) },
              () => '查看商品',
            )
          : null,
        row.status === 'failed'
          ? h(
              AppButton,
              { size: 'small', onClick: () => retry([row.id]) },
              () => '重试',
            )
          : null,
      ]),
  },
])
</script>

<template>
  <div class="selection-panel collection-tasks-panel">
    <ErrorState
      v-if="loadError"
      :description="loadError"
      retryable
      @retry="loadService"
    />
    <LoadingState v-else-if="!service" />
    <PageSection v-else-if="!service.available">
      <EmptyState :description="COLLECTION_TASKS_UNAVAILABLE" />
    </PageSection>
    <template v-else>
      <PageSection class="collection-task-composer">
        <ContextSwitchBar
          label="采集平台"
          appearance="bare"
          :items="platformItems"
          :active-key="platform"
          @select="setPlatform"
        >
          <template #icon="{ item }">
            <PlatformIcon :code="item.key as PlatformCode" />
          </template>
        </ContextSwitchBar>
        <template v-if="platform === 'douyin'">
          <AppRadio v-model="inputMode" :options="inputModeOptions" />
          <div class="collection-task-composer__entry">
            <AppInput
              v-model="draft"
              type="textarea"
              :placeholder="
                inputMode === 'product'
                  ? '每行输入一个抖音商品 ID 或链接'
                  : '每行输入一个已有店铺口令'
              "
              :maxlength="4000"
              aria-label="采集任务输入"
            />
            <AppButton tone="primary" :loading="busy" @click="createTasks">
              创建采集任务
            </AppButton>
          </div>
        </template>
        <NText v-else-if="platform === 'pdd'" depth="3">
          拼多多当前仅支持手机端手动返回资料；正式派发尚未接入。
        </NText>
        <NText v-else depth="3">淘宝商品资料采集正在规划中。</NText>
      </PageSection>

      <ManagementListSection density="compact">
        <ContextSwitchBar
          label="采集任务状态"
          appearance="bare"
          :items="statusItems"
          :active-key="status ?? 'all'"
          @select="setStatus"
        />
        <FilterBar density="compact">
          <FilterField width="lg">
            <AppInput
              v-model="keyword"
              placeholder="搜索商品标题、ID或提交内容"
              clearable
              @keyup.enter="searchTasks"
            />
          </FilterField>
          <FilterField width="sm">
            <AppSelect
              :model-value="filterPlatform ?? 'all'"
              :options="platformOptions"
              @update:model-value="setFilterPlatform"
            />
          </FilterField>
          <template #actions>
            <AppButton @click="searchTasks">查询</AppButton>
          </template>
        </FilterBar>
        <TableToolbar density="compact">
          <span v-if="selected.length">已选 {{ selected.length }} 项</span>
          <template #actions>
            <NTooltip>
              <template #trigger>
                <span>
                  <AppButton
                    size="small"
                    :disabled="!selected.length || busy"
                    @click="retry(selected.map(String))"
                    >批量重试</AppButton
                  >
                </span>
              </template>
              仅失败任务可重试
            </NTooltip>
            <AppButton
              size="small"
              :disabled="!selected.length || busy"
              @click="cancel(selected.map(String))"
              >取消选中任务</AppButton
            >
          </template>
        </TableToolbar>
        <DataTable
          :columns="columns"
          :data="pageData?.items ?? []"
          :loading="loading"
          :error="listError"
          :row-key="(row) => row.id"
          :checked-row-keys="selected"
          :scroll-x="1028"
          viewport="fill"
          appearance="list"
          show-header-when-empty
          empty-description="暂无采集任务"
          @update:checked-row-keys="selected = $event"
          @retry="fetchList"
        />
        <PaginationBar
          v-model:page="page"
          :page-size="pageSize"
          :item-count="pageData?.total ?? 0"
          density="compact"
          @update:page-size="setTaskPageSize"
        />
      </ManagementListSection>
    </template>

    <CollectionTaskDetailDialog
      :show="Boolean(detail)"
      :task="detail"
      @update:show="detail = $event ? detail : null"
    />
  </div>
</template>

<style scoped>
.collection-task-composer :deep(.page-section__content) {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.collection-task-composer__entry {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: var(--space-3);
}

.collection-task-composer__entry :deep(textarea) {
  min-height: 72px;
}

:global(.collection-task-actions) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  white-space: nowrap;
}

@media (max-width: 900px) {
  .collection-task-composer__entry {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
