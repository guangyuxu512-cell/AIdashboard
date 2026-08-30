import { describe, expect, it, vi } from 'vitest'

import { createProductMaterialGroupFixtures } from '../__fixtures__/product-material-groups.fixture'
import { useAiAssetsVisualMock } from './useAiAssetsVisualMock'

function createLibrary() {
  const revokePreviewUrl = vi.fn()
  const library = useAiAssetsVisualMock(createProductMaterialGroupFixtures(), {
    createPreviewUrl: (file) => `blob:visual/${file.name}`,
    revokePreviewUrl,
    now: () => '2026-08-31T08:00:00.000Z',
  })
  return { library, revokePreviewUrl }
}

describe('useAiAssetsVisualMock', () => {
  it('switches products and roles while clearing the selected asset', () => {
    const { library } = createLibrary()
    const source = library.visibleAssets.value[0]
    expect(source).toBeDefined()
    library.selectAsset(source!.assetId)
    expect(library.selectedAsset.value?.assetId).toBe(source!.assetId)

    library.selectProduct('pmg-mug')
    expect(library.selectedProduct.value?.name).toBe('马克杯')
    expect(library.selectedAsset.value).toBeNull()
    expect(library.roleCounts.value).toEqual({
      PRODUCT_SOURCE: 4,
      STYLE_REFERENCE: 0,
      AI_OUTPUT: 2,
    })

    library.selectAsset(library.visibleAssets.value[0]!.assetId)
    library.setActiveRole('STYLE_REFERENCE')
    expect(library.activeRole.value).toBe('STYLE_REFERENCE')
    expect(library.selectedAsset.value).toBeNull()
    expect(library.visibleAssets.value).toHaveLength(0)
  })

  it('creates, renames and deletes a product material group in local state', () => {
    const { library } = createLibrary()
    const created = library.createProduct({
      name: '  新产品  ',
      sku: ' SKU-NEW ',
    })

    expect(library.groups.value).toHaveLength(6)
    expect(library.selectedProduct.value).toMatchObject({
      id: created.id,
      name: '新产品',
      sku: 'SKU-NEW',
      enabled: true,
      defaultTemplateGroupId: null,
    })

    library.renameProduct(created.id, { name: '新品 A', sku: '' })
    expect(library.selectedProduct.value).toMatchObject({
      name: '新品 A',
      sku: undefined,
    })

    library.deleteProduct(created.id)
    expect(library.groups.value).toHaveLength(5)
    expect(library.groups.value.some((group) => group.id === created.id)).toBe(
      false,
    )
    expect(library.selectedAsset.value).toBeNull()
  })

  it('preserves eligibility values while the product is disabled', () => {
    const { library } = createLibrary()
    expect(library.selectedProduct.value).toMatchObject({
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
      defaultTemplateGroupId: 'tg-standard-a',
    })

    library.setProductEnabled(false)
    expect(library.childEligibilityDisabled.value).toBe(true)
    expect(library.selectedProduct.value).toMatchObject({
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
    })

    library.setNormalGenerationEnabled(false)
    library.setStyleReplicationEnabled(false)
    expect(library.selectedProduct.value).toMatchObject({
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
    })

    library.setProductEnabled(true)
    library.setNormalGenerationEnabled(false)
    library.setStyleReplicationEnabled(false)
    library.setDefaultTemplateGroupId('tg-lifestyle')
    expect(library.selectedProduct.value).toMatchObject({
      normalGenerationEnabled: false,
      styleReplicationEnabled: false,
      defaultTemplateGroupId: 'tg-lifestyle',
    })

    library.setDefaultTemplateGroupId(null)
    expect(library.selectedProduct.value?.defaultTemplateGroupId).toBeNull()
  })

  it('updates the toggled product before an enabled filter advances selection', () => {
    const { library } = createLibrary()
    const phoneStand = library.groups.value.find(
      (product) => product.id === 'pmg-phone-stand',
    )!
    const mug = library.groups.value.find(
      (product) => product.id === 'pmg-mug',
    )!
    const mugUpdatedAt = mug.updatedAt

    library.productFilter.value = 'enabled'
    library.selectProduct(phoneStand.id)
    library.setProductEnabled(false)

    expect(library.selectedProduct.value?.id).toBe(mug.id)
    expect(phoneStand.updatedAt).toBe('2026-08-31T08:00:00.000Z')
    expect(mug.updatedAt).toBe(mugUpdatedAt)
  })

  it('uploads, moves and deletes local mock assets with dynamic counts', () => {
    const { library, revokePreviewUrl } = createLibrary()
    const initial = library.roleCounts.value
    expect(initial).toEqual({
      PRODUCT_SOURCE: 5,
      STYLE_REFERENCE: 3,
      AI_OUTPUT: 6,
    })

    const validFile = new File(['visual'], '新增素材.png', {
      type: 'image/png',
    })
    const invalidFile = new File(['visual'], '说明.txt', { type: 'text/plain' })
    expect(library.uploadFiles([validFile, invalidFile])).toEqual({
      added: 1,
      rejected: 1,
    })
    expect(library.roleCounts.value.PRODUCT_SOURCE).toBe(6)

    const uploaded = library.visibleAssets.value[0]!
    expect(uploaded).toMatchObject({
      name: '新增素材.png',
      role: 'PRODUCT_SOURCE',
      sourceType: 'LOCAL_UPLOAD',
      previewUrl: 'blob:visual/新增素材.png',
    })

    library.selectAsset(uploaded.assetId)
    library.changeAssetRole(uploaded.assetId, 'STYLE_REFERENCE')
    expect(library.activeRole.value).toBe('STYLE_REFERENCE')
    expect(library.roleCounts.value).toEqual({
      PRODUCT_SOURCE: 5,
      STYLE_REFERENCE: 4,
      AI_OUTPUT: 6,
    })

    library.deleteAsset(uploaded.assetId)
    expect(library.roleCounts.value.STYLE_REFERENCE).toBe(3)
    expect(library.selectedAsset.value).toBeNull()
    expect(revokePreviewUrl).toHaveBeenCalledWith('blob:visual/新增素材.png')

    library.setActiveRole('AI_OUTPUT')
    expect(library.uploadFiles([validFile])).toEqual({ added: 0, rejected: 1 })
    expect(library.roleCounts.value.AI_OUTPUT).toBe(6)
  })

  it('searches names, SKU and asset filenames and filters product status', () => {
    const { library } = createLibrary()

    library.searchQuery.value = 'BWB-500'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['保温杯'])

    library.searchQuery.value = '参考-珠宝台'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['戒指'])

    library.searchQuery.value = '手机支架'
    expect(library.visibleAssets.value).toHaveLength(5)

    library.searchQuery.value = ''
    library.productFilter.value = 'disabled'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['戒指'])

    library.productFilter.value = 'enabled'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['手机支架', '马克杯', '收纳盒', '保温杯'])
  })
})
