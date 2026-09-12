<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ListFilter, Upload } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'
import { useMessage } from 'naive-ui'

import { createProductMaterialGroupFixtures } from '../__fixtures__/product-material-groups.fixture'
import {
  TEMPLATE_GROUP_OPTIONS,
  type MaterialAssetReference,
  type MaterialRole,
  type ProductMaterialFilter,
  type ProductMaterialGroup,
  type ProductMaterialGroupInput,
} from '../model/types'
import { useAiAssetsVisualMock } from '../model/useAiAssetsVisualMock'
import MaterialBatchToolbar from './MaterialBatchToolbar.vue'
import MaterialAssetGrid from './MaterialAssetGrid.vue'
import MaterialAssetInspector from './MaterialAssetInspector.vue'
import MaterialRoleTabs from './MaterialRoleTabs.vue'
import ProductMaterialFormDialog from './ProductMaterialFormDialog.vue'
import ProductMaterialSettings from './ProductMaterialSettings.vue'
import ProductMaterialSidebar from './ProductMaterialSidebar.vue'
import {
  AiManagementLayout,
  AiManagementToolbar,
} from '@/features/ai-workbench'
import EmptyState from '@/shared/components/EmptyState.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import ThreePaneWorkbench from '@/shared/components/ThreePaneWorkbench.vue'
import { AppButton, AppDialog, AppInput, AppSwitch } from '@/shared/ui'

type PendingDelete =
  | { type: 'product'; product: ProductMaterialGroup }
  | { type: 'asset'; asset: MaterialAssetReference }
  | { type: 'assets'; assets: MaterialAssetReference[] }

const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
const productDialogShow = ref(false)
const productDialogMode = ref<'create' | 'rename'>('create')
const editingProduct = ref<ProductMaterialGroup | null>(null)
const pendingDelete = ref<PendingDelete | null>(null)
const previewAsset = ref<MaterialAssetReference | null>(null)

const library = useAiAssetsVisualMock(createProductMaterialGroupFixtures())
const {
  visibleProducts,
  selectedProductId,
  selectedProduct,
  selectedAssetId,
  selectedAsset,
  selectedAssetIds,
  selectedAssets,
  selectionMode,
  activeRole,
  searchQuery,
  productFilter,
  visibleAssets,
  totalAssets,
  currentPage,
  pageSize,
  currentPageSelectedCount,
  currentPageSelectionChecked,
  currentPageSelectionIndeterminate,
  roleCounts,
} = library

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
  if (target.type === 'product') {
    return `确认删除产品“${target.product.name}”？`
  }
  if (target.type === 'assets') {
    return `确认删除已选择的 ${target.assets.length} 个素材？`
  }
  return `确认删除“${target.asset.name}”？`
})

function setFilter(key: string | number): void {
  if (key === 'all' || key === 'enabled' || key === 'disabled') {
    productFilter.value = key as ProductMaterialFilter
  }
}

function chooseFiles(): void {
  fileInput.value?.click()
}

function uploadFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  if (files.length === 0) return
  const result = library.uploadFiles(files)
  if (result.added > 0) message.success('上传成功')
  if (result.rejected > 0) message.warning('仅支持 JPG、JPEG、PNG、WEBP')
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
  if (productDialogMode.value === 'create') {
    library.createProduct(input)
  } else if (editingProduct.value) {
    library.renameProduct(editingProduct.value.id, input)
  }
  productDialogShow.value = false
  editingProduct.value = null
}

function confirmDelete(): void {
  const target = pendingDelete.value
  if (!target) return
  if (target.type === 'product') {
    library.deleteProduct(target.product.id)
  } else if (target.type === 'asset') {
    library.deleteAsset(target.asset.assetId)
  } else {
    const removed = library.deleteSelectedAssets()
    if (removed > 0) message.success(`已删除 ${removed} 个素材`)
  }
  pendingDelete.value = null
}

function requestBatchDelete(): void {
  if (selectedAssets.value.length === 0) return
  pendingDelete.value = { type: 'assets', assets: [...selectedAssets.value] }
}

function triggerAssetDownload(asset: MaterialAssetReference): void {
  const anchor = document.createElement('a')
  anchor.href = asset.previewUrl
  anchor.download = asset.name
  anchor.rel = 'noopener'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
}

function downloadAsset(asset: MaterialAssetReference): void {
  triggerAssetDownload(asset)
  message.success('已开始下载')
}

function downloadSelectedAssets(): void {
  if (selectedAssets.value.length === 0) return
  for (const asset of selectedAssets.value) triggerAssetDownload(asset)
  message.success(`已开始下载 ${selectedAssets.value.length} 个素材`)
}

function updateAssetRole(role: MaterialRole): void {
  if (!selectedAsset.value) return
  library.changeAssetRole(selectedAsset.value.assetId, role)
}

onBeforeUnmount(library.dispose)
</script>

<template>
  <div class="ai-assets-visual-mock">
    <AiManagementToolbar label="素材库工具栏">
      <AppInput
        v-model="searchQuery"
        width="lg"
        placeholder="搜索素材"
        clearable
        aria-label="搜索素材"
      />
      <template #actions>
        <NDropdown trigger="click" :options="filterOptions" @select="setFilter">
          <AppButton :aria-label="`筛选：${filterLabel}`">
            <ListFilter :size="16" />
            筛选
          </AppButton>
        </NDropdown>
        <input
          ref="fileInput"
          class="ai-assets-visual-mock__file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          @change="uploadFiles"
        />
        <AppButton
          tone="primary"
          :disabled="!selectedProduct || activeRole === 'AI_OUTPUT'"
          aria-label="上传素材"
          @click="chooseFiles"
        >
          <Upload :size="16" />
          上传素材
        </AppButton>
      </template>
    </AiManagementToolbar>

    <AiManagementLayout
      class="ai-assets-visual-mock__layout"
      label="产品素材库"
    >
      <ThreePaneWorkbench class="ai-assets-workspace">
        <template #left>
          <ProductMaterialSidebar
            :products="visibleProducts"
            :selected-product-id="selectedProductId"
            @create="openCreateProduct"
            @select="library.selectProduct"
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
                  <strong>{{ selectedProduct.name }}</strong>
                  <span class="ai-assets-workspace__product-counts">
                    商品原图 {{ roleCounts.PRODUCT_SOURCE }} · AI 成品
                    {{ roleCounts.AI_OUTPUT }}
                    · 全部素材 {{ selectedProduct.assets.length }}
                  </span>
                </div>
                <label class="ai-assets-workspace__enabled">
                  <span>启用</span>
                  <AppSwitch
                    :model-value="selectedProduct.enabled"
                    :aria-label="`${selectedProduct.name}启用状态`"
                    @update:model-value="library.setProductEnabled"
                  />
                </label>
              </header>

              <MaterialRoleTabs
                :model-value="activeRole"
                :counts="roleCounts"
                @update:model-value="library.setActiveRole"
              />

              <MaterialBatchToolbar
                :selection-mode="selectionMode"
                :selected-count="currentPageSelectedCount"
                :current-page-count="visibleAssets.length"
                :checked="currentPageSelectionChecked"
                :indeterminate="currentPageSelectionIndeterminate"
                @start-selection="library.startSelectionMode"
                @toggle-all="library.setCurrentPageSelected"
                @download="downloadSelectedAssets"
                @remove="requestBatchDelete"
                @finish="library.finishSelectionMode"
              />

              <div class="ai-assets-workspace__asset-scroll">
                <MaterialAssetGrid
                  :assets="visibleAssets"
                  :selected-asset-id="selectedAssetId"
                  :selected-asset-ids="selectedAssetIds"
                  :selection-mode="selectionMode"
                  @select="library.selectAsset"
                  @update:selected="library.setAssetSelected"
                />
              </div>

              <PaginationBar
                class="ai-assets-workspace__pagination"
                :page="currentPage"
                :page-size="pageSize"
                :item-count="totalAssets"
                @update:page="library.setPage"
                @update:page-size="library.setPageSize"
              />
            </template>
            <EmptyState v-else description="暂无产品" />
          </section>
        </template>

        <template #right>
          <div class="ai-assets-workspace__inspector">
            <MaterialAssetInspector
              v-if="selectedAsset"
              :asset="selectedAsset"
              @close="library.selectAsset(null)"
              @preview="previewAsset = $event"
              @download="downloadAsset"
              @remove="pendingDelete = { type: 'asset', asset: $event }"
              @update:role="updateAssetRole"
            />
            <ProductMaterialSettings
              v-else-if="selectedProduct"
              :product="selectedProduct"
              :template-group-options="TEMPLATE_GROUP_OPTIONS"
              @update:enabled="library.setProductEnabled"
              @update:normal-generation-enabled="
                library.setNormalGenerationEnabled
              "
              @update:style-replication-enabled="
                library.setStyleReplicationEnabled
              "
              @update:normal-template-group-ids="
                library.setNormalTemplateGroupIds
              "
              @update:style-replication-template-group-ids="
                library.setStyleReplicationTemplateGroupIds
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

    <AppDialog
      :show="Boolean(previewAsset)"
      :title="previewAsset?.name ?? '预览'"
      size="lg"
      positive-text="关闭"
      :show-negative="false"
      @update:show="previewAsset = null"
      @confirm="previewAsset = null"
    >
      <img
        v-if="previewAsset"
        class="ai-assets-visual-mock__preview-image"
        :src="previewAsset.previewUrl"
        :alt="previewAsset.name"
      />
    </AppDialog>
  </div>
</template>

<style scoped>
.ai-assets-visual-mock {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}

.ai-assets-visual-mock__file-input {
  display: none;
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
.ai-assets-workspace__enabled {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ai-assets-workspace__product-header {
  flex: 0 0 auto;
  justify-content: space-between;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.ai-assets-workspace__product-identity {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.ai-assets-workspace__product-identity strong,
.ai-assets-workspace__product-identity span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-assets-workspace__product-identity strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.ai-assets-workspace__product-counts {
  min-width: 0;
  overflow: visible;
  color: var(--text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.4;
  text-overflow: clip;
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
  overflow-y: auto;
  scrollbar-width: none;
}

.ai-assets-workspace__asset-scroll::-webkit-scrollbar {
  display: none;
}

.ai-assets-workspace__asset-scroll {
  min-height: 0;
  flex: 1;
  padding: var(--space-3) var(--space-1);
}

.ai-assets-workspace__pagination {
  flex: 0 0 auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.ai-assets-visual-mock__preview-image {
  display: block;
  max-width: 100%;
  max-height: calc(var(--dialog-max-height) - var(--field-width-sm));
  margin: 0 auto;
  border-radius: var(--radius-card);
  object-fit: contain;
}
</style>
