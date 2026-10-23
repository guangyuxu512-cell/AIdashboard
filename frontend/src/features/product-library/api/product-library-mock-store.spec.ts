import { beforeEach, describe, expect, it } from 'vitest'
import {
  createProductLibraryMockService,
  resetProductLibraryMockStore,
} from './product-library-mock-store'

describe('product library mock boundary', () => {
  beforeEach(() => resetProductLibraryMockStore())

  it('uses twenty rows by default and keeps product ids as strings', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(page.items).toHaveLength(20)
    expect(page.total).toBeGreaterThan(20)
    expect(page.items.every((item) => typeof item.productId === 'string')).toBe(
      true,
    )
    expect(page.items.some((item) => item.currentPrice === null)).toBe(true)
  })

  it('filters groups and mutates only the explicit mock store', async () => {
    const service = createProductLibraryMockService()
    const initial = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    const group = await service.createGroup('演示新分组')
    expect(await service.moveToGroup([initial.items[0]!.id], group.id)).toBe(1)
    const filtered = await service.list({
      keyword: '',
      platform: null,
      groupId: group.id,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(filtered.items).toHaveLength(1)
    expect(filtered.items[0]?.groupName).toBe('演示新分组')
  })

  it('creates collection tasks through the shared mock-only entry', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(await service.recollect([page.items[1]!.id])).toBeGreaterThanOrEqual(
      0,
    )
  })

  it('persists an explicit edit draft without changing source identities', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    const source = await service.detail(page.items[0]!.id)
    const saved = await service.saveEdit(source.id, {
      title: '已编辑的演示商品标题',
      attributes: source.attributes.map((attribute, index) => ({
        ...attribute,
        value: index === 0 ? '食品级不锈钢' : attribute.value,
      })),
      specDimensions: source.specDimensions.map((dimension, index) => ({
        ...dimension,
        name: index === 0 ? '表面颜色' : dimension.name,
      })),
      skus: source.skus.map((sku, index) => ({
        draftKey: sku.draftKey,
        sourceSkuId: sku.sourceSkuId,
        name: index === 0 ? '原色标准款' : sku.name,
        currentPrice: index === 0 ? null : '39.90',
        imageUrl: sku.imageUrl,
        specValues: {
          ...sku.specValues,
          color: index === 0 ? '原色' : '升级色',
        },
      })),
    })

    expect(saved).toMatchObject({
      id: source.id,
      productId: source.productId,
      platform: source.platform,
      title: '已编辑的演示商品标题',
      mockEditedAt: expect.any(String),
    })
    expect(saved.skus[0]).toMatchObject({
      draftKey: source.skus[0]!.draftKey,
      sourceSkuId: source.skus[0]!.sourceSkuId,
      name: '原色标准款',
      currentPrice: null,
      specValues: { color: '原色' },
    })
    expect((await service.detail(source.id)).title).toBe('已编辑的演示商品标题')

    resetProductLibraryMockStore()
    expect((await service.detail(source.id)).title).toBe(source.title)
  })

  it('adds and removes draft SKUs without shifting source image bindings', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      view: 'all',
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    const source = await service.detail(page.items[0]!.id)
    const retained = source.skus[1]!
    const saved = await service.saveEdit(source.id, {
      title: source.title,
      attributes: source.attributes,
      specDimensions: source.specDimensions,
      skus: [
        {
          draftKey: retained.draftKey,
          sourceSkuId: retained.sourceSkuId,
          name: retained.name,
          currentPrice: retained.currentPrice,
          imageUrl: retained.imageUrl,
          specValues: retained.specValues,
        },
        {
          draftKey: 'draft-sku-test',
          sourceSkuId: null,
          name: '前端新增规格',
          currentPrice: '49.90',
          imageUrl: null,
          specValues: { color: '测试色', model: '测试款' },
        },
      ],
    })

    expect(saved.skus).toHaveLength(2)
    expect(saved.skus[0]).toMatchObject({
      draftKey: retained.draftKey,
      sourceSkuId: retained.sourceSkuId,
      imageUrl: retained.imageUrl,
    })
    expect(saved.skus[1]).toMatchObject({
      draftKey: 'draft-sku-test',
      sourceSkuId: null,
      imageUrl: null,
      stockLabel: null,
    })
    expect(
      saved.skus.some((sku) => sku.draftKey === source.skus[0]!.draftKey),
    ).toBe(false)
    expect((await service.detail(source.id)).skus).toEqual(saved.skus)
  })
})
