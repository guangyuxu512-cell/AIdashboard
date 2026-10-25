<script setup lang="ts">
import { computed, h, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
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
import { useAuthStore } from '@/stores/auth'
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
const auth = useAuthStore()
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
const pendingSubmission = ref<{ signature: string; key: string } | null>(null)
const keyword = ref('')
const filterPlatform = ref<PlatformCode | null>(null)
const status = ref<CollectionTaskStatus | null>(null)
const page = ref(1)
const pageSize = ref(20)
let revision = 0
let listRevision = 0
let detailRevision = 0
let mounted = true
let pollTimer: ReturnType<typeof setTimeout> | null = null
const canWrite = computed(
  () => service.value?.mode === 'mock' || auth.hasTeamContext,
)
const writeHint = computed(() =>
  canWrite.value ? undefined : '请先选择具体团队后再操作',
)

function isCurrent(current: number) {
  return mounted && current === revision
}

function clearPoll() {
  if (pollTimer !== null) clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePoll() {
  clearPoll()
  if (
    !mounted ||
    service.value?.mode !== 'real' ||
    !pageData.value?.items.some((item) =>
      ['pending', 'running'].includes(item.status),
    )
  )
    return
  pollTimer = setTimeout(() => void fetchList(true), 2000)
}

onBeforeUnmount(() => {
  mounted = false
  revision += 1
  clearPoll()
})

const platformItems = computed(() =>
  (service.value?.mode === 'real'
    ? (['douyin'] as PlatformCode[])
    : (['douyin', 'pdd', 'taobao'] as PlatformCode[])
  ).map((code) => ({
    key: code,
    label: getPlatformDefinition(code)?.label ?? code,
  })),
)
const platformOptions = computed(() => [
  { label: '全部平台', value: 'all' },
  ...platformItems.value.map((item) => ({
    label: item.label,
    value: item.key,
  })),
])
const inputModeOptions = computed(() => [
  { label: '商品 ID／链接', value: 'product' },
  ...(service.value?.supportsShopCode
    ? [{ label: '店铺口令', value: 'shop-code' }]
    : []),
])
const statusLabels: Record<CollectionTaskStatus, string> = {
  pending: '排队中',
  running: '处理中',
  partial: '部分完成',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}
const statusTones = {
  pending: 'neutral',
  running: 'info',
  partial: 'warning',
  succeeded: 'success',
  failed: 'error',
  canceled: 'neutral',
} as const
const statusItems = computed(() => {
  if (!service.value?.supportsListFilters)
    return [{ key: 'all', label: '全部任务' }]
  const counts = pageData.value?.counts
  return [
    { key: 'all', label: `全部 ${counts?.all ?? 0}` },
    ...(
      [
        'pending',
        'running',
        'partial',
        'succeeded',
        'failed',
        'canceled',
      ] as const
    ).map((key) => ({
      key,
      label: `${statusLabels[key]} ${counts?.[key] ?? 0}`,
    })),
  ]
})

async function loadService() {
  clearPoll()
  const current = ++revision
  service.value = null
  pageData.value = null
  detail.value = null
  selected.value = []
  pendingSubmission.value = null
  listError.value = null
  loading.value = false
  busy.value = false
  loadError.value = null
  try {
    const resolved = await createCollectionTaskService(apiMode)
    if (isCurrent(current)) {
      service.value = resolved
      if (!resolved.supportsListFilters) {
        keyword.value = ''
        filterPlatform.value = null
        status.value = null
      }
      if (!resolved.supportsShopCode) inputMode.value = 'product'
      if (resolved.mode === 'real') platform.value = 'douyin'
    }
  } catch (error) {
    if (isCurrent(current))
      loadError.value = error instanceof Error ? error.message : '加载失败'
  }
}

async function fetchList(preserveSelection = false) {
  const source = service.value
  if (!mounted || !source?.available) return
  const current = revision
  const request = ++listRevision
  loading.value = true
  listError.value = null
  try {
    const result = await source.list({
      keyword: keyword.value.trim(),
      platform: filterPlatform.value,
      status: status.value,
      page: page.value,
      pageSize: pageSize.value,
    })
    if (!isCurrent(current) || request !== listRevision) return
    pageData.value = result
    page.value = result.page
    if (!preserveSelection) selected.value = []
    if (detail.value && source.mode === 'real') {
      const id = detail.value.id
      const detailRequest = detailRevision
      try {
        const result = await source.detail(id)
        if (
          isCurrent(current) &&
          detailRequest === detailRevision &&
          detail.value?.id === id
        )
          detail.value = result
      } catch {
        // Keep the last visible detail while the list remains refreshable.
      }
    }
  } catch (error) {
    if (isCurrent(current) && request === listRevision)
      listError.value =
        error instanceof Error ? error.message : '任务列表加载失败'
  } finally {
    if (isCurrent(current) && request === listRevision) {
      loading.value = false
      schedulePoll()
    }
  }
}

watch(
  () => props.contextKey,
  async () => {
    const context = props.contextKey
    await loadService()
    if (mounted && context === props.contextKey) await fetchList()
  },
  { immediate: true, flush: 'sync' },
)
watch([status, filterPlatform, page, pageSize], () => void fetchList())

function setPlatform(key: string) {
  platform.value = key as PlatformCode
  inputMode.value = 'product'
}

watch([draft, platform, inputMode], () => {
  pendingSubmission.value = null
})

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
  if (values.length > 100) return '每次最多提交 100 个商品'
  if (inputMode.value === 'shop-code') return null
  const invalid = values.find(
    (value) => !/^\d{8,}$/.test(value) && !/^https?:\/\/\S+$/i.test(value),
  )
  return invalid ? `无法识别：${invalid}` : null
}

async function createTasks() {
  if (!service.value?.available || busy.value || !canWrite.value) return
  const current = revision
  const values = parsedValues()
  const error = validate(values)
  if (error) {
    message.error(error)
    return
  }
  busy.value = true
  try {
    const signature = JSON.stringify({
      platform: platform.value,
      inputMode: inputMode.value,
      values,
    })
    if (pendingSubmission.value?.signature !== signature)
      pendingSubmission.value = { signature, key: crypto.randomUUID() }
    const result = await service.value.create({
      platform: platform.value,
      inputMode: inputMode.value,
      values,
      submissionKey: pendingSubmission.value.key,
    })
    if (!isCurrent(current)) return
    if (result.created.length) {
      const itemCount = result.created.reduce(
        (total, task) => total + task.itemCount,
        0,
      )
      message.success(
        result.created[0]?.reused
          ? '相同提交已存在，已复用原采集任务'
          : service.value.mode === 'mock'
            ? `已演示创建 ${result.created.length} 个采集任务；未向手机派发`
            : `已提交 ${itemCount} 个商品资料采集任务`,
      )
    }
    if (result.duplicates.length && !result.created[0]?.reused)
      message.info(
        service.value.mode === 'mock'
          ? `已跳过 ${result.duplicates.length} 个重复任务`
          : '相同提交已存在，已复用原采集任务',
      )
    if (result.created.length) draft.value = ''
    page.value = 1
    await fetchList()
  } catch (cause) {
    if (isCurrent(current))
      message.error(cause instanceof Error ? cause.message : '创建失败')
  } finally {
    if (isCurrent(current)) busy.value = false
  }
}

async function retry(ids: string[]) {
  if (!service.value?.available || busy.value || !canWrite.value) return
  const current = revision
  busy.value = true
  try {
    const count = await service.value.retry(ids)
    if (!isCurrent(current)) return
    message.info(count ? `已提交 ${count} 个明细重试` : '没有可有限重试的明细')
    await fetchList()
  } catch (error) {
    if (isCurrent(current))
      message.error(error instanceof Error ? error.message : '重试失败')
  } finally {
    if (isCurrent(current)) busy.value = false
  }
}

async function cancel(ids: string[]) {
  if (!service.value?.available || busy.value || !canWrite.value) return
  const current = revision
  busy.value = true
  try {
    const count = await service.value.cancel(ids)
    if (!isCurrent(current)) return
    message.info(count ? `已取消 ${count} 个采集请求` : '没有可取消的请求')
    await fetchList()
  } catch (error) {
    if (isCurrent(current))
      message.error(error instanceof Error ? error.message : '取消失败')
  } finally {
    if (isCurrent(current)) busy.value = false
  }
}

function viewProduct(row: CollectionTask) {
  void router.push({ path: '/products', query: { productId: row.productId } })
}

async function openDetail(row: CollectionTask) {
  if (!service.value?.available) return
  const current = revision
  const request = ++detailRevision
  try {
    const result = await service.value.detail(row.id)
    if (isCurrent(current) && request === detailRevision) detail.value = result
  } catch (error) {
    if (isCurrent(current) && request === detailRevision)
      message.error(error instanceof Error ? error.message : '任务详情加载失败')
  }
}

async function retryItem(itemId: string) {
  if (!service.value?.available || busy.value || !canWrite.value) return
  const current = revision
  const request = ++detailRevision
  busy.value = true
  try {
    const result = await service.value.retryItem(itemId)
    if (!isCurrent(current)) return
    if (request === detailRevision) detail.value = result
    message.success('已提交有限重试')
    await fetchList()
  } catch (error) {
    if (isCurrent(current))
      message.error(error instanceof Error ? error.message : '该明细不能重试')
  } finally {
    if (isCurrent(current)) busy.value = false
  }
}

async function recaptureItem(itemId: string) {
  if (!service.value?.available || busy.value || !canWrite.value) return
  const current = revision
  const request = ++detailRevision
  busy.value = true
  try {
    const result = await service.value.recaptureItem(itemId)
    if (!isCurrent(current)) return
    if (request === detailRevision) detail.value = result
    message.success('已提交重新采集')
    await fetchList()
  } catch (error) {
    if (isCurrent(current))
      message.error(error instanceof Error ? error.message : '重新采集失败')
  } finally {
    if (isCurrent(current)) busy.value = false
  }
}

const columns = computed<DataTableColumns<CollectionTask>>(() => [
  { type: 'selection', width: 44, fixed: 'left' },
  {
    title: '平台',
    key: 'platform',
    width: 112,
    align: 'center',
    render: (row) =>
      row.platform ? h(PlatformDisplay, { code: row.platform }) : '—',
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
          { tone: 'link', size: 'small', onClick: () => openDetail(row) },
          () => '详情',
        ),
        row.status === 'succeeded' && row.productId
          ? h(
              AppButton,
              { size: 'small', onClick: () => viewProduct(row) },
              () => '查看商品',
            )
          : null,
        row.status === 'failed' || row.status === 'partial'
          ? h(
              AppButton,
              {
                size: 'small',
                disabled: busy.value || !canWrite.value,
                title: writeHint.value,
                onClick: () => retry([row.id]),
              },
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
          <AppRadio
            v-if="service.supportsShopCode"
            v-model="inputMode"
            :options="inputModeOptions"
          />
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
            <AppButton
              tone="primary"
              :loading="busy"
              :disabled="!canWrite"
              :title="writeHint"
              @click="createTasks"
            >
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
          v-if="service.supportsListFilters"
          label="采集任务状态"
          appearance="bare"
          :items="statusItems"
          :active-key="status ?? 'all'"
          @select="setStatus"
        />
        <FilterBar class="collection-task-filter" density="compact">
          <template v-if="service.supportsListFilters">
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
          </template>
          <template #actions>
            <span v-if="selected.length">已选 {{ selected.length }} 项</span>
            <AppButton @click="searchTasks">查询</AppButton>
            <NTooltip>
              <template #trigger>
                <span>
                  <AppButton
                    size="small"
                    :disabled="!selected.length || busy || !canWrite"
                    @click="retry(selected.map(String))"
                    >批量重试</AppButton
                  >
                </span>
              </template>
              {{ writeHint ?? '仅失败任务可重试' }}
            </NTooltip>
            <AppButton
              size="small"
              :disabled="!selected.length || busy || !canWrite"
              :title="writeHint"
              @click="cancel(selected.map(String))"
              >取消选中任务</AppButton
            >
          </template>
        </FilterBar>
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
          @retry="() => fetchList()"
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
      :busy="busy || !canWrite"
      @update:show="detail = $event ? detail : null"
      @retry-item="retryItem"
      @recapture-item="recaptureItem"
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

.collection-task-filter :deep(.filter-bar__actions) {
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .collection-task-composer__entry {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
