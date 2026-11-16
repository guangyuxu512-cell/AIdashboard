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
  it('uses the product folder contract with independent template ID arrays', () => {
    const fixtures = createProductMaterialGroupFixtures()
    const phoneStand = fixtures.find(
      (product) => product.id === 'pmg-phone-stand',
    )

    expect(phoneStand).toMatchObject({
      enabled: true,
      normalGenerationEnabled: true,
      normalTemplateGroupIds: ['normal-standard-set', 'normal-lifestyle-set'],
      styleReplicationEnabled: true,
      styleReplicationTemplateGroupIds: [
        'style-competitor-a',
        'style-scene-replication',
      ],
    })
    expect(
      phoneStand?.assets.filter((asset) => asset.role === 'PRODUCT_SOURCE'),
    ).toHaveLength(31)
    expect(Object.keys(phoneStand!).sort()).toEqual(
      [
        'assets',
        'createdAt',
        'enabled',
        'id',
        'name',
        'normalGenerationEnabled',
        'normalTemplateGroupIds',
        'styleReplicationEnabled',
        'styleReplicationTemplateGroupIds',
        'updatedAt',
      ].sort(),
    )
  })

  it('paginates product source assets at 20 items per page', () => {
    const { library } = createLibrary()

    expect(library.pageSize.value).toBe(20)
    expect(library.totalAssets.value).toBe(31)
    expect(library.pageCount.value).toBe(2)
    expect(library.visibleAssets.value).toHaveLength(20)

    library.setPage(2)
    expect(library.currentPage.value).toBe(2)
    expect(library.visibleAssets.value).toHaveLength(11)
  })

  it('resets pagination and selection when the shared page size changes', () => {
    const { library } = createLibrary()

    library.setPage(2)
    library.startSelectionMode()
    library.setAssetSelected(library.visibleAssets.value[0]!.assetId, true)
    expect(library.currentPage.value).toBe(2)
    expect(library.selectedAssetIds.value).toHaveLength(1)

    library.setPageSize(10)
    expect(library.currentPage.value).toBe(1)
    expect(library.pageSize.value).toBe(10)
    expect(library.totalAssets.value).toBe(31)
    expect(library.pageCount.value).toBe(4)
    expect(library.visibleAssets.value).toHaveLength(10)
    expect(library.selectionMode.value).toBe(false)
    expect(library.selectedAssetIds.value).toEqual([])

    library.setPage(4)
    expect(library.visibleAssets.value).toHaveLength(1)

    library.setPageSize(50)
    expect(library.currentPage.value).toBe(1)
    expect(library.pageCount.value).toBe(1)
    expect(library.visibleAssets.value).toHaveLength(31)
  })

  it('selects one, some and all assets on the current page', () => {
    const { library } = createLibrary()
    const firstThree = library.visibleAssets.value.slice(0, 3)

    library.setAssetSelected(firstThree[0]!.assetId, true)
    expect(library.selectedAssetIds.value).toEqual([])

    library.startSelectionMode()
    expect(library.selectionMode.value).toBe(true)
    for (const asset of firstThree) {
      library.setAssetSelected(asset.assetId, true)
    }
    expect(library.currentPageSelectedCount.value).toBe(3)
    expect(library.currentPageSelectionIndeterminate.value).toBe(true)
    expect(library.currentPageSelectionChecked.value).toBe(false)

    library.setCurrentPageSelected(true)
    expect(library.selectedAssetIds.value).toHaveLength(20)
    expect(library.currentPageSelectionChecked.value).toBe(true)
    expect(library.currentPageSelectionIndeterminate.value).toBe(false)

    library.setAssetSelected(firstThree[0]!.assetId, false)
    expect(library.currentPageSelectedCount.value).toBe(19)
    expect(library.currentPageSelectionIndeterminate.value).toBe(true)

    library.setCurrentPageSelected(false)
    expect(library.selectedAssetIds.value).toEqual([])

    library.setCurrentPageSelected(true)
    library.finishSelectionMode()
    expect(library.selectionMode.value).toBe(false)
    expect(library.selectedAssetIds.value).toEqual([])
  })

  it('clears selection on page, role, product and search changes', () => {
    const { library } = createLibrary()
    const selectFirst = () => {
      library.startSelectionMode()
      const first = library.visibleAssets.value[0]!
      library.setAssetSelected(first.assetId, true)
    }

    selectFirst()
    library.setPage(2)
    expect(library.selectionMode.value).toBe(false)
    expect(library.selectedAssetIds.value).toEqual([])
    expect(library.selectedAsset.value).toBeNull()

    selectFirst()
    library.setActiveRole('STYLE_REFERENCE')
    expect(library.selectionMode.value).toBe(false)
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedAssetIds.value).toEqual([])
    expect(library.selectedAsset.value).toBeNull()

    selectFirst()
    library.selectProduct('pmg-mug')
    expect(library.selectionMode.value).toBe(false)
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedAssetIds.value).toEqual([])
    expect(library.selectedProduct.value?.name).toBe('马克杯')

    library.selectProduct('pmg-phone-stand')
    library.setActiveRole('PRODUCT_SOURCE')
    library.setPage(2)
    selectFirst()
    library.searchQuery.value = '商品素材-30'
    expect(library.selectionMode.value).toBe(false)
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedAssetIds.value).toEqual([])
    expect(library.totalAssets.value).toBe(1)
  })

  it('deletes the selected last page and returns to the previous valid page', () => {
    const { library } = createLibrary()
    library.setPage(2)
    library.setCurrentPageSelected(true)

    expect(library.selectedAssetIds.value).toHaveLength(11)
    expect(library.deleteSelectedAssets()).toBe(11)
    expect(library.roleCounts.value.PRODUCT_SOURCE).toBe(20)
    expect(library.totalAssets.value).toBe(20)
    expect(library.currentPage.value).toBe(1)
    expect(library.visibleAssets.value).toHaveLength(20)
    expect(library.selectedAssetIds.value).toEqual([])
  })

  it('deletes selected AI output relations through the shared batch path', () => {
    const { library } = createLibrary()
    library.setActiveRole('AI_OUTPUT')
    library.setCurrentPageSelected(true)

    expect(library.selectedAssetIds.value).toHaveLength(6)
    expect(library.deleteSelectedAssets()).toBe(6)
    expect(library.roleCounts.value.AI_OUTPUT).toBe(0)
    expect(library.currentPage.value).toBe(1)
    expect(library.visibleAssets.value).toEqual([])
    expect(library.selectedAssetIds.value).toEqual([])
  })

  it('creates, renames and deletes a product folder using name only', () => {
    const { library } = createLibrary()
    const created = library.createProduct({ name: '  新产品  ' })

    expect(library.groups.value).toHaveLength(6)
    expect(library.selectedProduct.value).toMatchObject({
      id: created.id,
      name: '新产品',
      enabled: true,
      normalGenerationEnabled: true,
      normalTemplateGroupIds: [],
      styleReplicationEnabled: false,
      styleReplicationTemplateGroupIds: [],
    })
    expect(Object.keys(library.selectedProduct.value!).sort()).toEqual(
      [
        'assets',
        'createdAt',
        'enabled',
        'id',
        'name',
        'normalGenerationEnabled',
        'normalTemplateGroupIds',
        'styleReplicationEnabled',
        'styleReplicationTemplateGroupIds',
        'updatedAt',
      ].sort(),
    )

    library.renameProduct(created.id, { name: '新品 A' })
    expect(library.selectedProduct.value?.name).toBe('新品 A')

    library.deleteProduct(created.id)
    expect(library.groups.value).toHaveLength(5)
    expect(library.groups.value.some((group) => group.id === created.id)).toBe(
      false,
    )
  })

  it('preserves template arrays while product or mode switches are off', () => {
    const { library } = createLibrary()
    const expected = {
      normalTemplateGroupIds: ['normal-standard-set', 'normal-lifestyle-set'],
      styleReplicationTemplateGroupIds: [
        'style-competitor-a',
        'style-scene-replication',
      ],
    }

    library.setProductEnabled(false)
    library.setNormalGenerationEnabled(false)
    library.setStyleReplicationEnabled(false)
    library.setNormalTemplateGroupIds([])
    library.setStyleReplicationTemplateGroupIds([])
    expect(library.selectedProduct.value).toMatchObject(expected)

    library.setProductEnabled(true)
    library.setNormalGenerationEnabled(false)
    library.setStyleReplicationEnabled(false)
    library.setNormalTemplateGroupIds([])
    library.setStyleReplicationTemplateGroupIds([])
    expect(library.selectedProduct.value).toMatchObject(expected)

    library.setNormalGenerationEnabled(true)
    library.setStyleReplicationEnabled(true)
    expect(library.selectedProduct.value).toMatchObject(expected)
  })

  it('updates each multi binding independently and rejects cross-mode IDs', () => {
    const { library } = createLibrary()

    library.setNormalTemplateGroupIds([
      'normal-minimal-main',
      'style-competitor-a',
      'normal-minimal-main',
    ])
    expect(library.selectedProduct.value).toMatchObject({
      normalTemplateGroupIds: ['normal-minimal-main'],
      styleReplicationTemplateGroupIds: [
        'style-competitor-a',
        'style-scene-replication',
      ],
    })

    library.setStyleReplicationTemplateGroupIds([
      'style-minimal-replication',
      'normal-standard-set',
    ])
    expect(library.selectedProduct.value).toMatchObject({
      normalTemplateGroupIds: ['normal-minimal-main'],
      styleReplicationTemplateGroupIds: ['style-minimal-replication'],
    })
  })

  it('uploads, moves and deletes local mock assets with dynamic counts', () => {
    const { library, revokePreviewUrl } = createLibrary()
    expect(library.roleCounts.value).toEqual({
      PRODUCT_SOURCE: 31,
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
    expect(library.roleCounts.value.PRODUCT_SOURCE).toBe(32)

    const uploaded = library.visibleAssets.value[0]!
    library.selectAsset(uploaded.assetId)
    library.changeAssetRole(uploaded.assetId, 'STYLE_REFERENCE')
    expect(library.roleCounts.value).toEqual({
      PRODUCT_SOURCE: 31,
      STYLE_REFERENCE: 4,
      AI_OUTPUT: 6,
    })

    library.deleteAsset(uploaded.assetId)
    expect(library.roleCounts.value.STYLE_REFERENCE).toBe(3)
    expect(revokePreviewUrl).toHaveBeenCalledWith('blob:visual/新增素材.png')

    library.setActiveRole('AI_OUTPUT')
    expect(library.uploadFiles([validFile])).toEqual({ added: 0, rejected: 1 })
  })

  it('searches product and asset names and filters product status', () => {
    const { library } = createLibrary()

    library.searchQuery.value = '户外场景'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['保温杯'])

    library.searchQuery.value = '参考-珠宝台'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['戒指'])

    library.searchQuery.value = '手机支架'
    expect(library.totalAssets.value).toBe(31)

    library.searchQuery.value = ''
    library.productFilter.value = 'disabled'
    expect(
      library.visibleProducts.value.map((product) => product.name),
    ).toEqual(['戒指'])
  })
})
