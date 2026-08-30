import { computed, ref, watch } from 'vue'

import type {
  MaterialAssetReference,
  MaterialRole,
  ProductMaterialFilter,
  ProductMaterialGroup,
  ProductMaterialGroupInput,
} from './types'

const SUPPORTED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

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
    assets: group.assets.map((asset) => ({ ...asset })),
  }))
}

function matches(value: string | undefined, query: string): boolean {
  return value?.toLocaleLowerCase().includes(query) ?? false
}

export function useAiAssetsVisualMock(
  initialGroups: readonly ProductMaterialGroup[],
  dependencies: VisualMockDependencies = {},
) {
  const groups = ref<ProductMaterialGroup[]>(cloneGroups(initialGroups))
  const selectedProductId = ref<string | null>(groups.value[0]?.id ?? null)
  const selectedAssetId = ref<string | null>(null)
  const activeRole = ref<MaterialRole>('PRODUCT_SOURCE')
  const searchQuery = ref('')
  const productFilter = ref<ProductMaterialFilter>('all')
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
        matches(group.sku, query) ||
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

  const visibleAssets = computed(() => {
    const product = selectedProduct.value
    if (!product) return []
    const query = searchQuery.value.trim().toLocaleLowerCase()
    const productIdentityMatches =
      !query || matches(product.name, query) || matches(product.sku, query)
    return product.assets.filter(
      (asset) =>
        asset.role === activeRole.value &&
        (productIdentityMatches || matches(asset.name, query)),
    )
  })

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

  watch(
    visibleProducts,
    (products) => {
      if (!products.some((product) => product.id === selectedProductId.value)) {
        selectedProductId.value = products[0]?.id ?? null
        selectedAssetId.value = null
      }
    },
    { flush: 'sync' },
  )

  function selectProduct(productId: string): void {
    if (!groups.value.some((group) => group.id === productId)) return
    selectedProductId.value = productId
    selectedAssetId.value = null
  }

  function selectAsset(assetId: string | null): void {
    if (
      assetId &&
      !selectedProduct.value?.assets.some((asset) => asset.assetId === assetId)
    ) {
      return
    }
    selectedAssetId.value = assetId
  }

  function setActiveRole(role: MaterialRole): void {
    activeRole.value = role
    selectedAssetId.value = null
  }

  function createProduct(
    input: ProductMaterialGroupInput,
  ): ProductMaterialGroup {
    localIdSequence += 1
    const timestamp = now()
    const product: ProductMaterialGroup = {
      id: `visual-product-${localIdSequence}`,
      name: input.name.trim(),
      sku: input.sku?.trim() || undefined,
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: false,
      defaultTemplateGroupId: null,
      createdAt: timestamp,
      updatedAt: timestamp,
      assets: [],
    }
    groups.value.push(product)
    searchQuery.value = ''
    productFilter.value = 'all'
    selectedProductId.value = product.id
    selectedAssetId.value = null
    activeRole.value = 'PRODUCT_SOURCE'
    return product
  }

  function renameProduct(
    productId: string,
    input: ProductMaterialGroupInput,
  ): void {
    const product = groups.value.find((group) => group.id === productId)
    if (!product) return
    product.name = input.name.trim()
    product.sku = input.sku?.trim() || undefined
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
      selectedAssetId.value = null
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

  function setDefaultTemplateGroupId(value: string | null): void {
    if (!selectedProduct.value) return
    selectedProduct.value.defaultTemplateGroupId = value
    selectedProduct.value.updatedAt = now()
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
    return { added, rejected }
  }

  function deleteAsset(assetId: string): void {
    const product = selectedProduct.value
    if (!product) return
    const index = product.assets.findIndex((asset) => asset.assetId === assetId)
    if (index < 0) return
    const [removed] = product.assets.splice(index, 1)
    if (removed?.objectUrl) revokePreviewUrl(removed.previewUrl)
    if (selectedAssetId.value === assetId) selectedAssetId.value = null
    product.updatedAt = now()
  }

  function changeAssetRole(assetId: string, role: MaterialRole): void {
    const asset = selectedProduct.value?.assets.find(
      (candidate) => candidate.assetId === assetId,
    )
    if (!asset || asset.role === 'AI_OUTPUT' || role === 'AI_OUTPUT') return
    asset.role = role
    activeRole.value = role
    selectedProduct.value!.updatedAt = now()
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
    activeRole,
    searchQuery,
    productFilter,
    visibleAssets,
    roleCounts,
    childEligibilityDisabled,
    selectProduct,
    selectAsset,
    setActiveRole,
    createProduct,
    renameProduct,
    deleteProduct,
    setProductEnabled,
    setNormalGenerationEnabled,
    setStyleReplicationEnabled,
    setDefaultTemplateGroupId,
    uploadFiles,
    deleteAsset,
    changeAssetRole,
    dispose,
  }
}
