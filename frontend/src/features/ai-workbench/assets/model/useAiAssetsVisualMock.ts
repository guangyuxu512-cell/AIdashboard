import { computed, ref, watch } from 'vue'

import {
  TEMPLATE_GROUP_OPTIONS,
  type GenerationMode,
  type MaterialAssetReference,
  type MaterialRole,
  type ProductMaterialFilter,
  type ProductMaterialGroup,
  type ProductMaterialGroupInput,
} from './types'

const SUPPORTED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
export const MATERIAL_ASSET_PAGE_SIZE = 20

interface VisualMockDependencies {
  createPreviewUrl?: (file: File) => string
  revokePreviewUrl?: (url: string) => void
  now?: () => string
}

export interface MockUploadResult {
  added: number
  rejected: number
}

function cloneGroups(
  groups: readonly ProductMaterialGroup[],
): ProductMaterialGroup[] {
  return groups.map((group) => ({
    ...group,
    normalTemplateGroupIds: [...group.normalTemplateGroupIds],
    styleReplicationTemplateGroupIds: [
      ...group.styleReplicationTemplateGroupIds,
    ],
    assets: group.assets.map((asset) => ({ ...asset })),
  }))
}

function matches(value: string | undefined, query: string): boolean {
  return value?.toLocaleLowerCase().includes(query) ?? false
}

function templateGroupIdsForMode(
  values: readonly string[],
  mode: GenerationMode,
): string[] {
  const allowedIds = new Set(
    TEMPLATE_GROUP_OPTIONS.filter((option) => option.mode === mode).map(
      (option) => option.id,
    ),
  )
  return [...new Set(values.filter((value) => allowedIds.has(value)))]
}

export function useAiAssetsVisualMock(
  initialGroups: readonly ProductMaterialGroup[],
  dependencies: VisualMockDependencies = {},
) {
  const groups = ref<ProductMaterialGroup[]>(cloneGroups(initialGroups))
  const selectedProductId = ref<string | null>(groups.value[0]?.id ?? null)
  const selectedAssetId = ref<string | null>(null)
  const selectedAssetIds = ref<string[]>([])
  const selectionMode = ref(false)
  const activeRole = ref<MaterialRole>('PRODUCT_SOURCE')
  const searchQuery = ref('')
  const productFilter = ref<ProductMaterialFilter>('all')
  const currentPage = ref(1)
  const pageSize = ref(MATERIAL_ASSET_PAGE_SIZE)
  let localIdSequence = 0

  const createPreviewUrl =
    dependencies.createPreviewUrl ?? ((file: File) => URL.createObjectURL(file))
  const revokePreviewUrl =
    dependencies.revokePreviewUrl ?? ((url: string) => URL.revokeObjectURL(url))
  const now = dependencies.now ?? (() => new Date().toISOString())

  const visibleProducts = computed(() => {
    const query = searchQuery.value.trim().toLocaleLowerCase()
    return groups.value.filter((group) => {
      const statusMatches =
        productFilter.value === 'all' ||
        (productFilter.value === 'enabled' && group.enabled) ||
        (productFilter.value === 'disabled' && !group.enabled)
      const queryMatches =
        !query ||
        matches(group.name, query) ||
        group.assets.some((asset) => matches(asset.name, query))
      return statusMatches && queryMatches
    })
  })

  const selectedProduct = computed(
    () =>
      groups.value.find((group) => group.id === selectedProductId.value) ??
      null,
  )

  const selectedAsset = computed(() => {
    if (!selectedProduct.value || !selectedAssetId.value) return null
    return (
      selectedProduct.value.assets.find(
        (asset) => asset.assetId === selectedAssetId.value,
      ) ?? null
    )
  })

  const filteredAssets = computed(() => {
    const product = selectedProduct.value
    if (!product) return []
    const query = searchQuery.value.trim().toLocaleLowerCase()
    const productIdentityMatches = !query || matches(product.name, query)
    return product.assets.filter(
      (asset) =>
        asset.role === activeRole.value &&
        (productIdentityMatches || matches(asset.name, query)),
    )
  })

  const totalAssets = computed(() => filteredAssets.value.length)
  const pageCount = computed(() =>
    Math.max(1, Math.ceil(totalAssets.value / pageSize.value)),
  )
  const visibleAssets = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return filteredAssets.value.slice(start, start + pageSize.value)
  })

  const selectedAssets = computed(() => {
    const product = selectedProduct.value
    if (!product) return []
    const selectedIds = new Set(selectedAssetIds.value)
    return product.assets.filter((asset) => selectedIds.has(asset.assetId))
  })

  const currentPageAssetIds = computed(() =>
    visibleAssets.value.map((asset) => asset.assetId),
  )
  const currentPageSelectedCount = computed(() => {
    const selectedIds = new Set(selectedAssetIds.value)
    return currentPageAssetIds.value.filter((assetId) =>
      selectedIds.has(assetId),
    ).length
  })
  const currentPageSelectionChecked = computed(
    () =>
      currentPageAssetIds.value.length > 0 &&
      currentPageSelectedCount.value === currentPageAssetIds.value.length,
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
      selectedProduct.value?.assets.filter(
        (asset) => asset.role === 'AI_OUTPUT',
      ).length ?? 0,
  }))

  const childEligibilityDisabled = computed(
    () => !selectedProduct.value?.enabled,
  )

  function clearAssetSelection(): void {
    selectedAssetIds.value = []
  }

  function startSelectionMode(): void {
    if (currentPageAssetIds.value.length === 0) return
    selectionMode.value = true
    selectedAssetId.value = null
  }

  function finishSelectionMode(): void {
    selectionMode.value = false
    clearAssetSelection()
  }

  function resetAssetContext(): void {
    currentPage.value = 1
    selectedAssetId.value = null
    finishSelectionMode()
  }

  watch(
    visibleProducts,
    (products) => {
      if (!products.some((product) => product.id === selectedProductId.value)) {
        selectedProductId.value = products[0]?.id ?? null
      }
    },
    { flush: 'sync' },
  )

  watch(selectedProductId, resetAssetContext, { flush: 'sync' })
  watch(searchQuery, resetAssetContext, { flush: 'sync' })

  function selectProduct(productId: string): void {
    if (!groups.value.some((group) => group.id === productId)) return
    if (selectedProductId.value === productId) return
    selectedProductId.value = productId
  }

  function selectAsset(assetId: string | null): void {
    if (selectionMode.value) return
    if (
      assetId &&
      !selectedProduct.value?.assets.some((asset) => asset.assetId === assetId)
    ) {
      return
    }
    selectedAssetId.value = assetId
  }

  function setAssetSelected(assetId: string, selected: boolean): void {
    if (!selectionMode.value) return
    if (!currentPageAssetIds.value.includes(assetId)) return
    const selectedIds = new Set(selectedAssetIds.value)
    if (selected) selectedIds.add(assetId)
    else selectedIds.delete(assetId)
    selectedAssetIds.value = [...selectedIds]
  }

  function setCurrentPageSelected(selected: boolean): void {
    if (selected) startSelectionMode()
    selectedAssetIds.value = selected ? [...currentPageAssetIds.value] : []
  }

  function setActiveRole(role: MaterialRole): void {
    activeRole.value = role
    resetAssetContext()
  }

  function setPage(page: number): void {
    const nextPage = Math.min(Math.max(1, page), pageCount.value)
    if (nextPage === currentPage.value) return
    currentPage.value = nextPage
    selectedAssetId.value = null
    finishSelectionMode()
  }

  function setPageSize(value: number): void {
    if (!Number.isInteger(value) || value <= 0 || value === pageSize.value) {
      return
    }
    pageSize.value = value
    resetAssetContext()
  }

  function createProduct(
    input: ProductMaterialGroupInput,
  ): ProductMaterialGroup {
    localIdSequence += 1
    const timestamp = now()
    const product: ProductMaterialGroup = {
      id: `visual-product-${localIdSequence}`,
      name: input.name.trim(),
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: false,
      normalTemplateGroupIds: [],
      styleReplicationTemplateGroupIds: [],
      createdAt: timestamp,
      updatedAt: timestamp,
      assets: [],
    }
    groups.value.push(product)
    searchQuery.value = ''
    productFilter.value = 'all'
    selectedProductId.value = product.id
    activeRole.value = 'PRODUCT_SOURCE'
    resetAssetContext()
    return product
  }

  function renameProduct(
    productId: string,
    input: ProductMaterialGroupInput,
  ): void {
    const product = groups.value.find((group) => group.id === productId)
    if (!product) return
    product.name = input.name.trim()
    product.updatedAt = now()
  }

  function revokeProductObjectUrls(product: ProductMaterialGroup): void {
    for (const asset of product.assets) {
      if (asset.objectUrl) revokePreviewUrl(asset.previewUrl)
    }
  }

  function deleteProduct(productId: string): void {
    const index = groups.value.findIndex((group) => group.id === productId)
    if (index < 0) return
    const [removed] = groups.value.splice(index, 1)
    if (removed) revokeProductObjectUrls(removed)
    if (selectedProductId.value === productId) {
      selectedProductId.value = visibleProducts.value[0]?.id ?? null
      resetAssetContext()
    }
  }

  function setProductEnabled(value: boolean): void {
    const product = selectedProduct.value
    if (!product) return
    product.enabled = value
    product.updatedAt = now()
  }

  function setNormalGenerationEnabled(value: boolean): void {
    if (!selectedProduct.value?.enabled) return
    selectedProduct.value.normalGenerationEnabled = value
    selectedProduct.value.updatedAt = now()
  }

  function setStyleReplicationEnabled(value: boolean): void {
    if (!selectedProduct.value?.enabled) return
    selectedProduct.value.styleReplicationEnabled = value
    selectedProduct.value.updatedAt = now()
  }

  function setNormalTemplateGroupIds(values: readonly string[]): void {
    const product = selectedProduct.value
    if (!product?.enabled || !product.normalGenerationEnabled) return
    product.normalTemplateGroupIds = templateGroupIdsForMode(
      values,
      'NORMAL_GENERATION',
    )
    product.updatedAt = now()
  }

  function setStyleReplicationTemplateGroupIds(
    values: readonly string[],
  ): void {
    const product = selectedProduct.value
    if (!product?.enabled || !product.styleReplicationEnabled) return
    product.styleReplicationTemplateGroupIds = templateGroupIdsForMode(
      values,
      'STYLE_REPLICATION',
    )
    product.updatedAt = now()
  }

  function uploadFiles(files: readonly File[]): MockUploadResult {
    const product = selectedProduct.value
    if (!product || activeRole.value === 'AI_OUTPUT') {
      return { added: 0, rejected: files.length }
    }

    let added = 0
    let rejected = 0
    for (const file of files) {
      if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
        rejected += 1
        continue
      }
      localIdSequence += 1
      const asset: MaterialAssetReference = {
        assetId: `visual-asset-${localIdSequence}`,
        name: file.name,
        mediaType: file.type,
        sourceType: 'LOCAL_UPLOAD',
        role: activeRole.value,
        previewUrl: createPreviewUrl(file),
        sizeBytes: file.size,
        objectUrl: true,
      }
      product.assets.unshift(asset)
      product.updatedAt = now()
      added += 1
    }
    if (added > 0) resetAssetContext()
    return { added, rejected }
  }

  function removeAssets(assetIds: readonly string[]): number {
    const product = selectedProduct.value
    if (!product) return 0
    const ids = new Set(assetIds)
    const removed = product.assets.filter((asset) => ids.has(asset.assetId))
    if (removed.length === 0) return 0
    product.assets = product.assets.filter((asset) => !ids.has(asset.assetId))
    for (const asset of removed) {
      if (asset.objectUrl) revokePreviewUrl(asset.previewUrl)
    }
    if (selectedAssetId.value && ids.has(selectedAssetId.value)) {
      selectedAssetId.value = null
    }
    clearAssetSelection()
    currentPage.value = Math.min(currentPage.value, pageCount.value)
    product.updatedAt = now()
    return removed.length
  }

  function deleteAsset(assetId: string): void {
    removeAssets([assetId])
  }

  function deleteSelectedAssets(): number {
    return removeAssets(selectedAssetIds.value)
  }

  function changeAssetRole(assetId: string, role: MaterialRole): void {
    const asset = selectedProduct.value?.assets.find(
      (candidate) => candidate.assetId === assetId,
    )
    if (!asset || asset.role === 'AI_OUTPUT' || role === 'AI_OUTPUT') return
    asset.role = role
    activeRole.value = role
    selectedProduct.value!.updatedAt = now()
    resetAssetContext()
  }

  function dispose(): void {
    for (const product of groups.value) revokeProductObjectUrls(product)
  }

  return {
    groups,
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
    filteredAssets,
    visibleAssets,
    totalAssets,
    currentPage,
    pageSize,
    pageCount,
    currentPageSelectedCount,
    currentPageSelectionChecked,
    currentPageSelectionIndeterminate,
    roleCounts,
    childEligibilityDisabled,
    selectProduct,
    selectAsset,
    startSelectionMode,
    finishSelectionMode,
    setAssetSelected,
    setCurrentPageSelected,
    clearAssetSelection,
    setActiveRole,
    setPage,
    setPageSize,
    createProduct,
    renameProduct,
    deleteProduct,
    setProductEnabled,
    setNormalGenerationEnabled,
    setStyleReplicationEnabled,
    setNormalTemplateGroupIds,
    setStyleReplicationTemplateGroupIds,
    uploadFiles,
    deleteAsset,
    deleteSelectedAssets,
    changeAssetRole,
    dispose,
  }
}
