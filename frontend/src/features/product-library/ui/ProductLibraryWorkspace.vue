<script setup lang="ts">
import { computed, h, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NEllipsis,
  NText,
  NTooltip,
  type DataTableColumns,
  type DataTableRowKey,
} from 'naive-ui'
import { useMessage } from 'naive-ui'
import { ProductImage } from '@/entities/product'
import {
  getPlatformDefinition,
  type PlatformCode,
} from '@/entities/platform/model/registry'
import { PlatformDisplay } from '@/entities/platform'
import { apiMode } from '@/shared/api'
import {
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  FilterField,
  LoadingState,
  ManagementListSection,
  PaginationBar,
  TableToolbar,
} from '@/shared/components'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'
import { useAuthStore } from '@/stores/auth'
import {
  createProductLibraryService,
  PRODUCT_LIBRARY_UNAVAILABLE,
} from '../api/product-library-service'
import type {
  LibraryProduct,
  ProductGroup,
  ProductLibraryPage,
  ProductLibraryService,
} from '../model/contracts'
import ProductExportDialog from './ProductExportDialog.vue'
import ProductGroupDialog from './ProductGroupDialog.vue'
import ProductImportDialog from './ProductImportDialog.vue'
import ProductPreviewDialog from './ProductPreviewDialog.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const contextKey = computed(
  () => `${auth.currentUser?.userId ?? 'none'}:${auth.activeTeamId ?? 'none'}`,
)
const service = shallowRef<ProductLibraryService | null>(null)
const groups = ref<ProductGroup[]>([])
const pageData = ref<ProductLibraryPage | null>(null)
const loadError = ref<string | null>(null)
const listError = ref<string | null>(null)
const loading = ref(false)
const busy = ref(false)
const keyword = ref('')
const platform = ref<PlatformCode | null>(null)
const groupId = ref<string | null>(null)
const category = ref<string | null>(null)
const page = ref(1)
const pageSize = ref(20)
const selected = ref<DataTableRowKey[]>([])
const preview = ref<LibraryProduct | null>(null)
const exportProducts = ref<LibraryProduct[]>([])
const importOpen = ref(false)
const groupDialogOpen = ref(false)
const groupDialogTitle = ref('移动商品分组')
const groupTargetIds = ref<string[]>([])
let revision = 0

const platformOptions = [
  { label: '全部平台', value: 'all' },
  ...(['douyin', 'pdd', 'taobao'] as PlatformCode[]).map((code) => ({
    label: getPlatformDefinition(code)?.label ?? code,
    value: code,
  })),
]
const groupOptions = computed(() => [
  { label: '全部分组', value: 'all' },
  { label: '未分组', value: 'ungrouped' },
  ...groups.value.map((group) => ({
    label: `${group.name}（${group.count}）`,
    value: group.id,
  })),
])
const categoryOptions = computed(() => [
  { label: '全部类目', value: 'all' },
  ...(pageData.value?.categories ?? []).map((item) => ({
    label: item,
    value: item,
  })),
])

async function loadService() {
  const current = ++revision
  service.value = null
  loadError.value = null
  try {
    const resolved = await createProductLibraryService(apiMode)
    if (current !== revision) return
    service.value = resolved
    if (!resolved.available) return
    groups.value = await resolved.groups()
  } catch (error) {
    if (current === revision)
      loadError.value =
        error instanceof Error ? error.message : '商品库加载失败'
  }
}

async function fetchList() {
  if (!service.value?.available) return
  loading.value = true
  listError.value = null
  try {
    const result = await service.value.list({
      keyword: keyword.value.trim(),
      platform: platform.value,
      groupId: groupId.value,
      category: category.value,
      page: page.value,
      pageSize: pageSize.value,
    })
    const items = result.items
    pageData.value = result
    page.value = result.page
    selected.value = []
    const requested =
      typeof route.query.productId === 'string' ? route.query.productId : null
    if (requested && !preview.value) {
      const match = items.find((item) => item.productId === requested)
      if (match) preview.value = await service.value.detail(match.id)
    }
  } catch (error) {
    listError.value =
      error instanceof Error ? error.message : '商品列表加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  contextKey,
  async () => {
    keyword.value =
      typeof route.query.productId === 'string' ? route.query.productId : ''
    await loadService()
    await fetchList()
  },
  { immediate: true },
)
watch([platform, groupId, category, page, pageSize], fetchList)

function reset() {
  keyword.value = ''
  platform.value = null
  groupId.value = null
  category.value = null
  page.value = 1
  void fetchList()
}

function searchList() {
  page.value = 1
  void fetchList()
}

function setPlatformFilter(value: string | number | null) {
  platform.value =
    value === 'all' || value === null ? null : (value as PlatformCode)
  page.value = 1
}

function setCategoryFilter(value: string | number | null) {
  category.value = value === 'all' || value === null ? null : String(value)
  page.value = 1
}

function setGroupFilter(value: string | number | null) {
  groupId.value = value === 'all' || value === null ? null : String(value)
  page.value = 1
}

function setProductPageSize(value: number) {
  pageSize.value = value
  page.value = 1
}

async function openPreview(row: LibraryProduct) {
  if (!service.value?.available) return
  try {
    preview.value = await service.value.detail(row.id)
    void router.replace({ query: { ...route.query, productId: row.productId } })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '商品详情加载失败')
  }
}

function closePreview(show: boolean) {
  if (show) return
  preview.value = null
  const query = { ...route.query }
  delete query.productId
  void router.replace({ query })
}

function openExport(rows: LibraryProduct[]) {
  exportProducts.value = rows
}

function selectedProducts(): LibraryProduct[] {
  const ids = new Set(selected.value.map(String))
  return (pageData.value?.items ?? []).filter((row) => ids.has(row.id))
}

function confirmExport() {
  message.info('已核对演示导出清单；未生成或下载真实文件')
  exportProducts.value = []
}

function confirmImport(payload: {
  files: File[]
  groupId: string | null
  mode: string
}) {
  message.info(
    `已演示选择 ${payload.files.length} 个${payload.mode.toUpperCase()}输入；未解析或写入商品库`,
  )
  importOpen.value = false
}

function openGroup(ids: string[], title = '移动商品分组') {
  groupTargetIds.value = ids
  groupDialogTitle.value = title
  groupDialogOpen.value = true
}

async function createGroup(name: string) {
  if (!service.value?.available || busy.value) return
  busy.value = true
  try {
    await service.value.createGroup(name)
    groups.value = await service.value.groups()
    message.info('已创建演示分组；未写入正式商品库')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建分组失败')
  } finally {
    busy.value = false
  }
}

async function moveGroup(target: string | null) {
  if (!service.value?.available || busy.value || !groupTargetIds.value.length)
    return
  busy.value = true
  try {
    const count = await service.value.moveToGroup(groupTargetIds.value, target)
    groups.value = await service.value.groups()
    message.info(`已演示移动 ${count} 个商品；未写入正式商品库`)
    groupDialogOpen.value = false
    selected.value = []
    if (preview.value && groupTargetIds.value.includes(preview.value.id))
      preview.value = await service.value.detail(preview.value.id)
    await fetchList()
  } finally {
    busy.value = false
  }
}

async function recollectSelected() {
  if (!service.value?.available || busy.value || !selected.value.length) return
  busy.value = true
  try {
    const count = await service.value.recollect(selected.value.map(String))
    message.info(`已演示创建 ${count} 个重新采集任务；未向手机派发`)
    selected.value = []
  } finally {
    busy.value = false
  }
}

async function removeSelected() {
  if (!service.value?.available || busy.value || !selected.value.length) return
  busy.value = true
  try {
    const count = await service.value.remove(selected.value.map(String))
    message.info(`已从演示列表移除 ${count} 个商品；未修改正式商品库`)
    selected.value = []
    groups.value = await service.value.groups()
    await fetchList()
  } finally {
    busy.value = false
  }
}

const columns = computed<DataTableColumns<LibraryProduct>>(() => [
  { type: 'selection', width: 44, fixed: 'left' },
  {
    title: '商品标题',
    key: 'title',
    width: 360,
    fixed: 'left',
    render: (row) =>
      h('div', { class: 'product-library-title' }, [
        h(ProductImage, {
          src: row.mainImageUrl,
          title: row.title,
          size: 'thumbnail',
          density: 'compact',
        }),
        h('div', { class: 'product-library-title__text' }, [
          h(NEllipsis, { tooltip: true, lineClamp: 2 }, () => row.title),
          h(NText, { depth: 3 }, () => row.groupName ?? '未分组'),
        ]),
      ]),
  },
  {
    title: '来源商品',
    key: 'source',
    width: 220,
    align: 'center',
    render: (row) =>
      h('div', { class: 'product-library-source' }, [
        h(PlatformDisplay, { code: row.platform }),
        h(NTooltip, null, {
          trigger: () => h('span', row.productId),
          default: () => row.productId,
        }),
      ]),
  },
  {
    title: '类目',
    key: 'category',
    width: 360,
    align: 'center',
    render: (row) =>
      row.category
        ? h(
            NEllipsis,
            {
              class: 'product-library-category',
              tooltip: true,
              lineClamp: 2,
            },
            () => row.category,
          )
        : h(NText, { depth: 3 }, () => '—'),
  },
  {
    title: '当前价格',
    key: 'price',
    width: 112,
    align: 'center',
    render: (row) =>
      row.currentPrice === null
        ? h(NText, { depth: 3 }, () => '—')
        : `¥${row.currentPrice}`,
  },
  {
    title: '采集时间',
    key: 'collectedAt',
    width: 176,
    align: 'center',
    render: (row) => row.collectedAt.replace('T', ' ').slice(0, 16),
  },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h('div', { class: 'product-library-actions' }, [
        h(
          AppButton,
          { tone: 'link', size: 'small', onClick: () => openPreview(row) },
          () => '预览',
        ),
        h(
          AppButton,
          { size: 'small', onClick: () => openExport([row]) },
          () => '导出 TXT',
        ),
      ]),
  },
])
</script>

<template>
  <ErrorState
    v-if="loadError"
    :description="loadError"
    retryable
    @retry="loadService"
  />
  <LoadingState v-else-if="!service" />
  <EmptyState
    v-else-if="!service.available"
    :description="PRODUCT_LIBRARY_UNAVAILABLE"
  />
  <div v-else class="product-library-workspace">
    <FilterBar density="compact">
      <FilterField width="lg">
        <AppInput
          v-model="keyword"
          placeholder="搜索商品标题、商品 ID 或类目"
          clearable
          @keyup.enter="searchList"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          :model-value="platform ?? 'all'"
          :options="platformOptions"
          @update:model-value="setPlatformFilter"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          :model-value="category ?? 'all'"
          :options="categoryOptions"
          @update:model-value="setCategoryFilter"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          :model-value="groupId ?? 'all'"
          :options="groupOptions"
          @update:model-value="setGroupFilter"
        />
      </FilterField>
      <template #actions>
        <AppButton @click="reset">重置</AppButton>
        <AppButton @click="searchList">查询</AppButton>
      </template>
      <template #primary-action>
        <AppButton @click="openGroup([], '新建商品分组')">新建分组</AppButton>
        <AppButton tone="primary" @click="importOpen = true"
          >导入资料包</AppButton
        >
      </template>
    </FilterBar>

    <ManagementListSection density="compact">
      <TableToolbar density="compact">
        <span v-if="selected.length">已选 {{ selected.length }} 项</span>
        <template #actions>
          <AppButton
            size="small"
            :disabled="!selected.length"
            @click="openExport(selectedProducts())"
          >
            批量导出 TXT
          </AppButton>
          <AppButton
            size="small"
            :disabled="!selected.length"
            @click="openGroup(selected.map(String))"
          >
            移动分组
          </AppButton>
          <AppButton
            size="small"
            :disabled="!selected.length || busy"
            @click="recollectSelected"
          >
            重新采集
          </AppButton>
          <AppButton
            tone="danger"
            size="small"
            :disabled="!selected.length || busy"
            @click="removeSelected"
          >
            删除
          </AppButton>
        </template>
      </TableToolbar>
      <DataTable
        :columns="columns"
        :data="pageData?.items ?? []"
        :loading="loading"
        :error="listError"
        :row-key="(row) => row.id"
        :checked-row-keys="selected"
        :scroll-x="1432"
        viewport="fill"
        appearance="list"
        show-header-when-empty
        empty-description="暂无商品资料"
        @update:checked-row-keys="selected = $event"
        @retry="fetchList"
      />
      <PaginationBar
        v-model:page="page"
        :page-size="pageSize"
        :item-count="pageData?.total ?? 0"
        density="compact"
        @update:page-size="setProductPageSize"
      />
    </ManagementListSection>

    <ProductPreviewDialog
      :show="Boolean(preview)"
      :product="preview"
      @update:show="closePreview"
      @export="openExport([$event])"
      @group="openGroup([$event.id])"
    />
    <ProductExportDialog
      :show="Boolean(exportProducts.length)"
      :products="exportProducts"
      @update:show="exportProducts = $event ? exportProducts : []"
      @confirm="confirmExport"
    />
    <ProductImportDialog
      :show="importOpen"
      :groups="groups"
      @update:show="importOpen = $event"
      @confirm="confirmImport"
    />
    <ProductGroupDialog
      :show="groupDialogOpen"
      :groups="groups"
      :count="groupTargetIds.length"
      :loading="busy"
      :title="groupDialogTitle"
      @update:show="groupDialogOpen = $event"
      @create="createGroup"
      @confirm="moveGroup"
    />
  </div>
</template>

<style scoped>
.product-library-workspace {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}
:global(.product-library-title) {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
}
:global(.product-library-title__text) {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-1);
}
:global(.product-library-source) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}
:global(.product-library-category) {
  width: 100%;
  text-align: center;
}
:global(.product-library-actions) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  white-space: nowrap;
}
</style>
