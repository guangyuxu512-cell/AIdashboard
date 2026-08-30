<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ListFilter, Upload } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'
import { useMessage } from 'naive-ui'

import { createProductMaterialGroupFixtures } from '../__fixtures__/product-material-groups.fixture'
import {
  type MaterialAssetReference,
  type MaterialRole,
  type ProductMaterialFilter,
  type ProductMaterialGroup,
  type ProductMaterialGroupInput,
} from '../model/types'
import { useAiAssetsVisualMock } from '../model/useAiAssetsVisualMock'
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
import { AppButton, AppDialog, AppInput, AppSwitch } from '@/shared/ui'

type PendingDelete =
  | { type: 'product'; product: ProductMaterialGroup }
  | { type: 'asset'; asset: MaterialAssetReference }

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
  activeRole,
  searchQuery,
  productFilter,
  visibleAssets,
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

const deleteDialogTitle = computed(() =>
  pendingDelete.value?.type === 'product' ? '删除产品' : '删除素材',
)

const deleteDialogText = computed(() => {
  const target = pendingDelete.value
  if (!target) return ''
  return target.type === 'product'
    ? `确认删除产品“${target.product.name}”？`
    : `确认删除“${target.asset.name}”？`
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
  if (target.type === 'product') library.deleteProduct(target.product.id)
  else library.deleteAsset(target.asset.assetId)
  pendingDelete.value = null
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
      <div class="ai-assets-workspace">
        <aside class="ai-assets-workspace__panel ai-assets-workspace__sidebar">
          <ProductMaterialSidebar
            :products="visibleProducts"
            :selected-product-id="selectedProductId"
            @create="openCreateProduct"
            @select="library.selectProduct"
            @rename="openRenameProduct"
            @remove="pendingDelete = { type: 'product', product: $event }"
          />
        </aside>

        <section
          class="ai-assets-workspace__panel ai-assets-workspace__library"
          aria-label="当前产品素材"
        >
          <template v-if="selectedProduct">
            <header class="ai-assets-workspace__product-header">
              <div class="ai-assets-workspace__product-identity">
                <strong>{{ selectedProduct.name }}</strong>
                <span v-if="selectedProduct.sku">{{
                  selectedProduct.sku
                }}</span>
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

            <div class="ai-assets-workspace__asset-scroll">
              <MaterialAssetGrid
                :assets="visibleAssets"
                :selected-asset-id="selectedAssetId"
                @select="library.selectAsset"
              />
            </div>
          </template>
          <EmptyState v-else description="暂无产品" />
        </section>

        <aside
          class="ai-assets-workspace__panel ai-assets-workspace__inspector"
        >
          <MaterialAssetInspector
            v-if="selectedAsset"
            :asset="selectedAsset"
            @close="library.selectAsset(null)"
            @preview="previewAsset = $event"
            @remove="pendingDelete = { type: 'asset', asset: $event }"
            @update:role="updateAssetRole"
          />
          <ProductMaterialSettings
            v-else-if="selectedProduct"
            :product="selectedProduct"
            @update:enabled="library.setProductEnabled"
            @update:normal-generation-enabled="
              library.setNormalGenerationEnabled
            "
            @update:style-replication-enabled="
              library.setStyleReplicationEnabled
            "
            @update:default-template-group-id="
              library.setDefaultTemplateGroupId
            "
          />
          <EmptyState v-else description="暂无产品" />
        </aside>
      </div>
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

.ai-assets-workspace {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  gap: var(--layout-card-gap);
  grid-template-columns:
    var(--field-width-md)
    minmax(var(--field-width-md), 1fr)
    var(--field-width-lg);
  overflow: hidden;
}

.ai-assets-workspace__panel {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface-solid);
}

.ai-assets-workspace__sidebar,
.ai-assets-workspace__inspector {
  background: var(--bg-subtle);
}

.ai-assets-workspace__library {
  display: flex;
  flex-direction: column;
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

.ai-assets-workspace__product-identity span,
.ai-assets-workspace__enabled span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.ai-assets-workspace__library :deep(.material-role-tabs) {
  margin: var(--space-3) 0;
}

.ai-assets-workspace__asset-scroll,
.ai-assets-workspace__inspector {
  overflow-y: auto;
  scrollbar-width: none;
}

.ai-assets-workspace__asset-scroll::-webkit-scrollbar,
.ai-assets-workspace__inspector::-webkit-scrollbar {
  display: none;
}

.ai-assets-workspace__asset-scroll {
  min-height: 0;
  flex: 1;
  padding: var(--space-1);
}

.ai-assets-visual-mock__preview-image {
  display: block;
  max-width: 100%;
  max-height: calc(var(--dialog-max-height) - var(--field-width-sm));
  margin: 0 auto;
  border-radius: var(--radius-card);
  object-fit: contain;
}

@media (max-width: 1200px) {
  .ai-assets-workspace {
    grid-template-columns:
      var(--field-width-sm)
      minmax(var(--field-width-md), 1fr)
      var(--field-width-md);
  }
}

@media (max-width: 940px) {
  .ai-assets-workspace {
    grid-template-columns: var(--field-width-sm) minmax(0, 1fr);
    overflow-y: auto;
    scrollbar-width: none;
  }

  .ai-assets-workspace::-webkit-scrollbar {
    display: none;
  }

  .ai-assets-workspace__sidebar,
  .ai-assets-workspace__library {
    min-height: var(--field-width-xl);
  }

  .ai-assets-workspace__inspector {
    min-height: var(--field-width-lg);
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .ai-assets-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .ai-assets-workspace__inspector {
    grid-column: auto;
  }
}
</style>
