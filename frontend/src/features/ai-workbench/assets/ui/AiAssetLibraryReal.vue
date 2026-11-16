<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { ListFilter, Upload } from '@lucide/vue'
import { NDropdown, NUpload } from 'naive-ui'
import type { DropdownOption, UploadSettledFileInfo } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  AssetDownloadStatusBar,
  AssetPreviewDialog,
  formatAssetDownloadFailure,
  useAssetDownloadQueue,
} from '@/entities/asset'
import { formatAssetOperationFailure } from '@/entities/asset/api/asset-api'
import { aiAssetApi } from '@/entities/ai-workbench/api/ai-asset-api'
import { aiWorkbenchApi, aiWorkbenchQueryKeys } from '@/entities/ai-workbench'
import {
  AiManagementLayout,
  AiManagementToolbar,
} from '@/features/ai-workbench'
import { getErrorMessage } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import ThreePaneWorkbench from '@/shared/components/ThreePaneWorkbench.vue'
import { AppButton, AppDialog, AppInput, AppSwitch } from '@/shared/ui'

import type {
  MaterialAssetReference,
  MaterialRole,
  ProductMaterialFilter,
  ProductMaterialGroup,
  ProductMaterialGroupInput,
  TemplateGroupOption,
} from '../model/types'
import { mapProductMaterialGroup } from '../../real-api/model/mappers'
import MaterialAssetGrid from './MaterialAssetGrid.vue'
import MaterialAssetInspector from './MaterialAssetInspector.vue'
import MaterialBatchToolbar from './MaterialBatchToolbar.vue'
import MaterialRoleTabs from './MaterialRoleTabs.vue'
import ProductMaterialFormDialog from './ProductMaterialFormDialog.vue'
import ProductMaterialSettings from './ProductMaterialSettings.vue'
import ProductMaterialSidebar from './ProductMaterialSidebar.vue'

type PendingDelete =
  | { type: 'product'; product: ProductMaterialGroup }
  | { type: 'asset'; asset: MaterialAssetReference }
  | { type: 'assets'; assets: MaterialAssetReference[] }

const message = useMessage()
const auth = useAuthStore()
const canWrite = computed(() => auth.hasTeamContext)
const actorContextKey = () =>
  `${auth.currentUser?.userId ?? ''}:${auth.activeTeamId ?? ''}`
const queryClient = useQueryClient()
const downloads = useAssetDownloadQueue()
const productDialogShow = ref(false)
const productDialogMode = ref<'create' | 'rename'>('create')
const editingProduct = ref<ProductMaterialGroup | null>(null)
const pendingDelete = ref<PendingDelete | null>(null)
const previewAsset = ref<MaterialAssetReference | null>(null)
const selectedProductId = ref<string | null>(null)
const selectedAssetId = ref<string | null>(null)
const selectedAssetIds = ref<string[]>([])
const selectionMode = ref(false)
const activeRole = ref<MaterialRole>('PRODUCT_SOURCE')
const searchDraft = ref('')
const searchQuery = ref('')
const autoSearch = useAutoSearch(() => {
  searchQuery.value = searchDraft.value
})
const productFilter = ref<ProductMaterialFilter>('all')
const currentPage = ref(1)
const pageSize = ref(20)

const groupsQuery = useQuery({
  queryKey: aiWorkbenchQueryKeys.materials,
  queryFn: async () => {
    const summaries = await aiWorkbenchApi.listAllProductMaterialGroups()
    return Promise.all(
      summaries.map((group) =>
        aiWorkbenchApi.getProductMaterialGroup(group.material_group_id),
      ),
    )
  },
  select: (groups) => groups.map(mapProductMaterialGroup),
})

const templateOptionsQuery = useQuery({
  queryKey: [...aiWorkbenchQueryKeys.templates, 'binding-options'],
  queryFn: () => aiWorkbenchApi.listAllTemplateGroups(),
  select: (groups): TemplateGroupOption[] =>
    groups.map((group) => ({
      id: group.template_group_id,
      label: group.name,
      mode: group.mode,
    })),
})

const actionMutation = useMutation({
  mutationFn: (action: () => Promise<void>) => action(),
  onSuccess: () =>
    queryClient.invalidateQueries({ queryKey: aiWorkbenchQueryKeys.materials }),
})

const products = computed(() => groupsQuery.data.value ?? [])
const visibleProducts = computed(() =>
  products.value.filter((product) => {
    if (productFilter.value === 'enabled') return product.enabled
    if (productFilter.value === 'disabled') return !product.enabled
    return true
  }),
)
const selectedProduct = computed(
  () =>
    products.value.find((product) => product.id === selectedProductId.value) ??
    null,
)
const roleAssets = computed(
  () =>
    selectedProduct.value?.assets.filter(
      (asset) =>
        asset.role === activeRole.value &&
        (!searchQuery.value.trim() ||
          asset.name
            .toLocaleLowerCase()
            .includes(searchQuery.value.trim().toLocaleLowerCase())),
    ) ?? [],
)
const totalAssets = computed(() => roleAssets.value.length)
const pageCount = computed(() =>
  Math.max(1, Math.ceil(totalAssets.value / pageSize.value)),
)
const visibleAssets = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return roleAssets.value.slice(start, start + pageSize.value)
})
const selectedAsset = computed(
  () =>
    selectedProduct.value?.assets.find(
      (asset) => asset.assetId === selectedAssetId.value,
    ) ?? null,
)
const selectedAssets = computed(() =>
  visibleAssets.value.filter((asset) =>
    selectedAssetIds.value.includes(asset.assetId),
  ),
)
const currentPageSelectedCount = computed(() => selectedAssets.value.length)
const currentPageSelectionChecked = computed(
  () =>
    visibleAssets.value.length > 0 &&
    currentPageSelectedCount.value === visibleAssets.value.length,
)
const currentPageSelectionIndeterminate = computed(
  () =>
    currentPageSelectedCount.value > 0 && !currentPageSelectionChecked.value,
)
const roleCounts = computed<Record<MaterialRole, number>>(() => ({
  PRODUCT_SOURCE:
    selectedProduct.value?.assets.filter(
      (asset) => asset.role === 'PRODUCT_SOURCE',
    ).length ?? 0,
  STYLE_REFERENCE:
    selectedProduct.value?.assets.filter(
      (asset) => asset.role === 'STYLE_REFERENCE',
    ).length ?? 0,
  AI_OUTPUT:
    selectedProduct.value?.assets.filter((asset) => asset.role === 'AI_OUTPUT')
      .length ?? 0,
}))

const filterOptions: DropdownOption[] = [
  { key: 'all', label: '全部' },
  { key: 'enabled', label: '已启用产品' },
  { key: 'disabled', label: '已停用产品' },
]
const filterLabel = computed(
  () =>
    filterOptions.find((option) => option.key === productFilter.value)?.label ??
    '全部',
)
const deleteDialogTitle = computed(() => {
  if (pendingDelete.value?.type === 'product') return '删除产品'
  if (pendingDelete.value?.type === 'assets') return '批量删除素材'
  return '删除素材'
})
const deleteDialogText = computed(() => {
  const target = pendingDelete.value
  if (!target) return ''
  if (target.type === 'product') return `确认删除产品“${target.product.name}”？`
  if (target.type === 'assets') {
    return `确认从当前产品移除已选择的 ${target.assets.length} 个素材？`
  }
  return `确认从当前产品移除“${target.asset.name}”？`
})

watch(
  visibleProducts,
  (next) => {
    if (!next.some((product) => product.id === selectedProductId.value)) {
      selectedProductId.value = next[0]?.id ?? null
    }
  },
  { immediate: true, flush: 'sync' },
)
watch([selectedProductId, activeRole], resetSelection)
watch(
  actorContextKey,
  () => {
    productDialogShow.value = false
    editingProduct.value = null
    pendingDelete.value = null
    previewAsset.value = null
    selectedProductId.value = null
    resetSelection()
  },
  { flush: 'sync' },
)
watch(searchQuery, () => {
  currentPage.value = 1
  resetSelection()
})

function resetSelection(): void {
  selectionMode.value = false
  selectedAssetIds.value = []
  selectedAssetId.value = null
  currentPage.value = 1
}

async function execute(action: () => Promise<void>, success?: string) {
  if (!canWrite.value) {
    message.warning('请先选择具体团队')
    return
  }
  const context = actorContextKey()
  try {
    await actionMutation.mutateAsync(action)
    if (success && context === actorContextKey()) message.success(success)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

function reload(): void {
  void groupsQuery.refetch()
  void templateOptionsQuery.refetch()
}

function setFilter(key: string | number): void {
  if (key === 'all' || key === 'enabled' || key === 'disabled') {
    productFilter.value = key
  }
}

function selectProduct(id: string): void {
  selectedProductId.value = id
  // Re-selecting the current product must close an open asset inspector too.
  // The selectedProductId watcher only runs when the id changes.
  selectedAssetId.value = null
  selectionMode.value = false
  selectedAssetIds.value = []
}

function setActiveRole(role: MaterialRole): void {
  activeRole.value = role
}

function openCreateProduct(): void {
  productDialogMode.value = 'create'
  editingProduct.value = null
  productDialogShow.value = true
}

function openRenameProduct(product: ProductMaterialGroup): void {
  productDialogMode.value = 'rename'
  editingProduct.value = product
  productDialogShow.value = true
}

function saveProduct(input: ProductMaterialGroupInput): void {
  const editing = editingProduct.value
  const mode = productDialogMode.value
  productDialogShow.value = false
  editingProduct.value = null
  void execute(
    async () => {
      if (mode === 'create') {
        const created = await aiWorkbenchApi.createProductMaterialGroup({
          name: input.name.trim(),
        })
        selectedProductId.value = created.material_group_id
        return
      }
      if (editing) {
        await aiWorkbenchApi.updateProductMaterialGroup(editing.id, {
          name: input.name.trim(),
        })
      }
    },
    mode === 'create' ? '产品已创建' : '产品已更新',
  )
}

function updateProduct(
  data: Parameters<typeof aiWorkbenchApi.updateProductMaterialGroup>[1],
  success?: string,
): void {
  const id = selectedProductId.value
  if (!id) return
  void execute(async () => {
    await aiWorkbenchApi.updateProductMaterialGroup(id, data)
  }, success)
}

function uploadFile({ file }: { file: UploadSettledFileInfo }): boolean {
  if (!canWrite.value) return false
  const context = actorContextKey()
  const selectedFile = file.file
  const groupId = selectedProductId.value
  const role = activeRole.value
  if (!groupId || role === 'AI_OUTPUT' || !selectedFile) return false
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(selectedFile.type)) {
    message.warning('仅支持 JPG、JPEG、PNG、WEBP')
    return false
  }
  void execute(async () => {
    const asset = await aiAssetApi.upload(selectedFile).catch((error) => {
      throw new Error(
        formatAssetOperationFailure(error, `上传 ${selectedFile.name}`),
      )
    })
    if (context !== actorContextKey()) {
      throw new Error('团队已切换，文件保留在原团队，未关联当前素材组')
    }
    try {
      await aiWorkbenchApi.attachAsset(groupId, asset.asset_id, role)
    } catch (error) {
      if (context !== actorContextKey()) {
        throw new Error('团队已切换，原团队的文件未自动清理')
      }
      const failure = formatAssetOperationFailure(
        error,
        `关联 ${selectedFile.name}`,
      )
      try {
        await aiAssetApi.cleanup(asset.asset_id)
      } catch (cleanupError) {
        throw new Error(
          `${failure}；已上传文件清理未完成：${formatAssetOperationFailure(cleanupError, '清理')}`,
        )
      }
      throw new Error(`${failure}；本次未关联文件已清理`)
    }
  }, '素材已上传')
  return false
}

function selectAsset(assetId: string): void {
  selectedAssetId.value = assetId
}

function setAssetSelected(assetId: string, selected: boolean): void {
  selectedAssetIds.value = selected
    ? [...new Set([...selectedAssetIds.value, assetId])]
    : selectedAssetIds.value.filter((id) => id !== assetId)
}

function startSelectionMode(): void {
  selectionMode.value = true
  selectedAssetId.value = null
}

function finishSelectionMode(): void {
  selectionMode.value = false
  selectedAssetIds.value = []
}

function setCurrentPageSelected(selected: boolean): void {
  selectionMode.value = true
  selectedAssetId.value = null
  const pageIds = new Set(visibleAssets.value.map((asset) => asset.assetId))
  selectedAssetIds.value = selected
    ? [...new Set([...selectedAssetIds.value, ...pageIds])]
    : selectedAssetIds.value.filter((id) => !pageIds.has(id))
}

function setPage(value: number): void {
  currentPage.value = Math.min(Math.max(1, value), pageCount.value)
  finishSelectionMode()
  selectedAssetId.value = null
}

function setPageSize(value: number): void {
  pageSize.value = value
  currentPage.value = 1
  finishSelectionMode()
  selectedAssetId.value = null
}

function updateAssetRole(role: MaterialRole): void {
  const groupId = selectedProductId.value
  const assetId = selectedAssetId.value
  if (!groupId || !assetId || role === 'AI_OUTPUT') return
  void execute(async () => {
    await aiWorkbenchApi.attachAsset(groupId, assetId, role)
  }, '素材类型已更新')
}

function startAssetDownloads(assets: readonly MaterialAssetReference[]): void {
  if (!assets.length || downloads.isDownloading.value) return
  void downloads
    .start(
      assets.map((asset) => ({
        id: asset.assetId,
        contentUrl: asset.previewUrl,
        filename: asset.name,
      })),
    )
    .then((summary) => {
      if (!summary) return
      if (summary.succeeded)
        message.success(`已开始下载 ${summary.succeeded} 个素材`)
      const firstFailure = summary.results.find(
        (result) => result.failure,
      )?.failure
      if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
    })
}

function downloadAsset(asset: MaterialAssetReference): void {
  startAssetDownloads([asset])
}

function downloadPreviewAsset(source: {
  id: string
  name: string
  contentUrl: string
}): void {
  startAssetDownloads([
    {
      assetId: source.id,
      name: source.name,
      previewUrl: source.contentUrl,
      mediaType: '',
      sourceType: 'LOCAL_UPLOAD',
      role: activeRole.value,
    },
  ])
}

function setPreviewVisible(visible: boolean): void {
  if (!visible) previewAsset.value = null
}

function downloadSelectedAssets(): void {
  startAssetDownloads([...selectedAssets.value])
}

function retryFailedDownloads(): void {
  void downloads.retryFailed().then((summary) => {
    if (!summary) return
    if (summary.succeeded)
      message.success(`已重新下载 ${summary.succeeded} 个素材`)
    const firstFailure = summary.results.find(
      (result) => result.failure,
    )?.failure
    if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
  })
}

function confirmDelete(): void {
  const target = pendingDelete.value
  const groupId = selectedProductId.value
  pendingDelete.value = null
  if (!target) return
  if (target.type === 'product') {
    void execute(async () => {
      await aiWorkbenchApi.deleteProductMaterialGroup(target.product.id)
      if (selectedProductId.value === target.product.id)
        selectedProductId.value = null
    }, '产品已删除')
    return
  }
  if (!groupId) return
  const assets = target.type === 'assets' ? target.assets : [target.asset]
  void execute(
    async () => {
      await Promise.all(
        assets.map((asset) =>
          aiWorkbenchApi.detachAsset(groupId, asset.assetId),
        ),
      )
      finishSelectionMode()
      selectedAssetId.value = null
    },
    assets.length > 1 ? `已移除 ${assets.length} 个素材` : '素材已移除',
  )
}

function replaceBindings(
  mode: 'NORMAL_GENERATION' | 'STYLE_REPLICATION',
  ids: string[],
): void {
  const groupId = selectedProductId.value
  if (!groupId) return
  void execute(async () => {
    await aiWorkbenchApi.replaceTemplateBindings(groupId, mode, ids)
  }, '模板绑定已更新')
}
</script>

<template>
  <div class="ai-assets-real">
    <AiManagementToolbar label="素材库工具栏">
      <AppInput
        v-model="searchDraft"
        width="lg"
        placeholder="搜索素材"
        clearable
        aria-label="搜索素材"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(searchDraft)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
      <template #actions>
        <NDropdown trigger="click" :options="filterOptions" @select="setFilter">
          <AppButton :aria-label="`筛选：${filterLabel}`">
            <ListFilter :size="16" />
            筛选
          </AppButton>
        </NDropdown>
        <NUpload
          class="ai-assets-real__upload"
          accept="image/jpeg,image/png,image/webp"
          multiple
          :show-file-list="false"
          :disabled="
            !canWrite || !selectedProduct || activeRole === 'AI_OUTPUT'
          "
          :input-props="{ 'aria-label': '上传素材' }"
          :on-before-upload="uploadFile"
        >
          <AppButton
            tone="primary"
            :disabled="
              !canWrite || !selectedProduct || activeRole === 'AI_OUTPUT'
            "
          >
            <Upload :size="16" />
            上传素材
          </AppButton>
        </NUpload>
      </template>
    </AiManagementToolbar>

    <AiManagementLayout class="ai-assets-real__layout" label="产品素材库">
      <LoadingState
        v-if="
          groupsQuery.isPending.value || templateOptionsQuery.isPending.value
        "
        description="正在加载素材库"
      />
      <ErrorState
        v-else-if="
          groupsQuery.isError.value || templateOptionsQuery.isError.value
        "
        :description="
          getErrorMessage(
            groupsQuery.error.value ?? templateOptionsQuery.error.value,
          )
        "
        retryable
        @retry="reload"
      />
      <ThreePaneWorkbench v-else class="ai-assets-workspace">
        <template #left>
          <ProductMaterialSidebar
            :read-only="!canWrite"
            :products="visibleProducts"
            :selected-product-id="selectedProductId"
            @create="openCreateProduct"
            @select="selectProduct"
            @rename="openRenameProduct"
            @remove="pendingDelete = { type: 'product', product: $event }"
          />
        </template>

        <template #main>
          <section
            class="ai-assets-workspace__library"
            aria-label="当前产品素材"
          >
            <template v-if="selectedProduct">
              <header class="ai-assets-workspace__product-header">
                <div class="ai-assets-workspace__product-identity">
                  <strong :title="selectedProduct.name">{{
                    selectedProduct.name
                  }}</strong>
                  <span class="ai-assets-workspace__product-counts">
                    商品原图 {{ roleCounts.PRODUCT_SOURCE }} · AI 成品
                    {{ roleCounts.AI_OUTPUT }} · 全部素材
                    {{ selectedProduct.assets.length }}
                  </span>
                </div>
                <label class="ai-assets-workspace__enabled">
                  <span>启用</span>
                  <AppSwitch
                    :model-value="selectedProduct.enabled"
                    :disabled="!canWrite"
                    :aria-label="`${selectedProduct.name}启用状态`"
                    @update:model-value="updateProduct({ enabled: $event })"
                  />
                </label>
              </header>

              <MaterialRoleTabs
                :model-value="activeRole"
                :counts="roleCounts"
                @update:model-value="setActiveRole"
              />
              <MaterialBatchToolbar
                :read-only="!canWrite"
                :selection-mode="selectionMode"
                :selected-count="currentPageSelectedCount"
                :current-page-count="visibleAssets.length"
                :checked="currentPageSelectionChecked"
                :indeterminate="currentPageSelectionIndeterminate"
                @start-selection="startSelectionMode"
                @toggle-all="setCurrentPageSelected"
                @download="downloadSelectedAssets"
                @remove="
                  selectedAssets.length &&
                  (pendingDelete = {
                    type: 'assets',
                    assets: [...selectedAssets],
                  })
                "
                @finish="finishSelectionMode"
              />
              <AssetDownloadStatusBar
                :is-downloading="downloads.isDownloading.value"
                :progress-label="downloads.progressLabel.value"
                :failed-count="downloads.failedRequests.value.length"
                @cancel="downloads.cancel"
                @retry-failed="retryFailedDownloads"
              />

              <div class="ai-assets-workspace__asset-scroll">
                <MaterialAssetGrid
                  :assets="visibleAssets"
                  :selected-asset-id="selectedAssetId"
                  :selected-asset-ids="selectedAssetIds"
                  :selection-mode="selectionMode"
                  @select="selectAsset"
                  @update:selected="setAssetSelected"
                />
              </div>
              <PaginationBar
                class="ai-assets-workspace__pagination"
                :page="currentPage"
                :page-size="pageSize"
                :item-count="totalAssets"
                @update:page="setPage"
                @update:page-size="setPageSize"
              />
            </template>
            <EmptyState v-else description="暂无产品" />
          </section>
        </template>

        <template #right>
          <div class="ai-assets-workspace__inspector">
            <MaterialAssetInspector
              :read-only="!canWrite"
              v-if="selectedAsset"
              :asset="selectedAsset"
              @close="selectedAssetId = null"
              @preview="previewAsset = $event"
              @download="downloadAsset"
              @remove="pendingDelete = { type: 'asset', asset: $event }"
              @update:role="updateAssetRole"
            />
            <ProductMaterialSettings
              :read-only="!canWrite"
              v-else-if="selectedProduct"
              :product="selectedProduct"
              :template-group-options="templateOptionsQuery.data.value ?? []"
              @update:enabled="updateProduct({ enabled: $event })"
              @update:normal-generation-enabled="
                updateProduct({ normal_generation_enabled: $event })
              "
              @update:style-replication-enabled="
                updateProduct({ style_replication_enabled: $event })
              "
              @update:normal-template-group-ids="
                replaceBindings('NORMAL_GENERATION', $event)
              "
              @update:style-replication-template-group-ids="
                replaceBindings('STYLE_REPLICATION', $event)
              "
            />
            <EmptyState v-else description="暂无产品" />
          </div>
        </template>
      </ThreePaneWorkbench>
    </AiManagementLayout>

    <ProductMaterialFormDialog
      :show="productDialogShow"
      :mode="productDialogMode"
      :product="editingProduct"
      @update:show="productDialogShow = $event"
      @save="saveProduct"
    />
    <AppDialog
      :show="Boolean(pendingDelete)"
      :title="deleteDialogTitle"
      size="sm"
      positive-text="删除"
      @update:show="pendingDelete = null"
      @confirm="confirmDelete"
    >
      {{ deleteDialogText }}
    </AppDialog>
    <AssetPreviewDialog
      :show="Boolean(previewAsset)"
      :items="
        roleAssets.map((asset) => ({
          id: asset.assetId,
          name: asset.name,
          contentUrl: asset.previewUrl,
        }))
      "
      :selected-asset-id="previewAsset?.assetId ?? null"
      @update:show="setPreviewVisible"
      @download="downloadPreviewAsset"
    />
  </div>
</template>

<style scoped>
.ai-assets-real {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}

.ai-assets-workspace__library,
.ai-assets-workspace__inspector {
  min-width: 0;
  min-height: 0;
  flex: 1;
}

.ai-assets-workspace__library {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: var(--space-4);
}

.ai-assets-workspace__product-header,
.ai-assets-workspace__product-identity,
.ai-assets-workspace__enabled {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ai-assets-workspace__product-header {
  flex: 0 0 auto;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.ai-assets-workspace__product-identity {
  min-width: 0;
  flex: 1 1 auto;
}

.ai-assets-workspace__product-identity > strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-assets-workspace__product-counts {
  min-width: 0;
  color: var(--text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.4;
  white-space: normal;
}

.ai-assets-workspace__enabled span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.ai-assets-workspace__library :deep(.material-role-tabs) {
  margin: var(--space-3) 0 0;
}

.ai-assets-workspace__asset-scroll {
  min-height: 0;
  flex: 1;
  padding: var(--space-3) var(--space-1);
  overflow-y: auto;
  scrollbar-width: none;
}

.ai-assets-workspace__asset-scroll::-webkit-scrollbar {
  display: none;
}

.ai-assets-workspace__pagination {
  flex: 0 0 auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.ai-assets-real__upload {
  width: auto;
  flex: 0 0 auto;
}
</style>
