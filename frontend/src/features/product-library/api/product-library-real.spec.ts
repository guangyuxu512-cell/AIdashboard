import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import { createProductLibraryRealService } from './product-library-real'

vi.mock('@/shared/api', () => ({
  httpClient: { get: vi.fn() },
}))

const product = {
  product_id: 'library-1',
  platform: 'douyin',
  source_product_id: '3832497447662387684',
  group_id: 'group-1',
  title: '真实入库商品',
  source_url: 'https://example.invalid/product',
  primary_image_url: 'https://example.invalid/image.webp',
  category_path: ['厨具', '储物器具'],
  current_sale_price_cent: 1299,
  currency: 'CNY',
  adopted_version_id: 'version-1',
  last_applied_capture_at: '2026-10-20T09:00:00+08:00',
  last_ingested_at: '2026-10-20T09:01:00+08:00',
  created_at: '2026-10-20T09:01:00+08:00',
  updated_at: '2026-10-20T09:01:00+08:00',
} as const

describe('product library Real adapter', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads groups and maps only authoritative list fields', async () => {
    vi.mocked(httpClient.get)
      .mockResolvedValueOnce({
        data: [{ group_id: 'group-1', name: '测试组' }],
      })
      .mockResolvedValueOnce({
        data: { items: [product], total: 1, page: 1, page_size: 20 },
      })
    const service = createProductLibraryRealService()
    expect(await service.groups()).toEqual([
      { id: 'group-1', name: '测试组', count: null },
    ])
    const page = await service.list({
      view: 'grouped',
      keyword: '真实',
      platform: null,
      groupId: 'group-1',
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(page.items[0]).toMatchObject({
      id: 'library-1',
      productId: '3832497447662387684',
      groupName: '测试组',
      category: '厨具 / 储物器具',
      currentPrice: '12.99',
      skus: [],
      attributes: [],
    })
    expect(httpClient.get).toHaveBeenLastCalledWith(
      '/api/v1/product-library/products',
      {
        params: {
          page: 1,
          page_size: 20,
          search: '真实',
          group_id: 'group-1',
          ungrouped: undefined,
        },
      },
    )
  })

  it('reads detail history without guessing UU snapshot fields', async () => {
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        ...product,
        merchant_snapshot: { name: '不猜字段' },
        latest_collection_state: 'succeeded',
        latest_collection_error_code: null,
        versions: [
          {
            version_id: 'version-1',
            captured_at: '2026-10-20T09:00:00+08:00',
            source_format_version: 1,
            cleaner_version: 'cleaner-1',
            raw_content_sha256: 'a'.repeat(64),
            uu_snapshot: { unknown: 'kept server-side' },
            price_evidence: {},
          },
        ],
      },
    })
    const detail = await createProductLibraryRealService().detail('library-1')
    expect(detail).toMatchObject({
      latestCollectionState: 'succeeded',
      detailImageUrls: [],
      history: [{ id: 'version-1', state: 'completed' }],
    })
    expect(detail.attributes).toEqual([])
  })

  it('exports only the adopted version complete UU snapshot as JSON TXT', async () => {
    const adoptedSnapshot = {
      schemaVersion: 2,
      productId: product.source_product_id,
      skuList: [{ skuId: 'sku-1', title: '中文规格' }],
      images: { detail: ['https://example.invalid/detail.webp'] },
    }
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        ...product,
        merchant_snapshot: null,
        latest_collection_state: 'succeeded',
        latest_collection_error_code: null,
        versions: [
          {
            version_id: 'version-old',
            captured_at: '2026-10-19T09:00:00+08:00',
            source_format_version: 1,
            cleaner_version: 'cleaner-1',
            raw_content_sha256: 'b'.repeat(64),
            uu_snapshot: { stale: true },
            price_evidence: {},
          },
          {
            version_id: 'version-1',
            captured_at: '2026-10-20T09:00:00+08:00',
            source_format_version: 2,
            cleaner_version: 'cleaner-2',
            raw_content_sha256: 'a'.repeat(64),
            uu_snapshot: adoptedSnapshot,
            price_evidence: {},
          },
        ],
      },
    })

    const file =
      await createProductLibraryRealService().exportSingle('library-1')

    expect(file.fileName).toBe(`${product.source_product_id}.txt`)
    expect(JSON.parse(file.content)).toEqual(adoptedSnapshot)
    expect(file.content).not.toContain('"stale"')
    expect(httpClient.get).toHaveBeenCalledWith(
      '/api/v1/product-library/products/library-1',
    )
  })

  it('refuses export when the adopted version is absent from detail', async () => {
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        ...product,
        merchant_snapshot: null,
        latest_collection_state: 'succeeded',
        latest_collection_error_code: null,
        versions: [],
      },
    })

    await expect(
      createProductLibraryRealService().exportSingle('library-1'),
    ).rejects.toThrow('已采用的资料版本未在商品详情中返回')
  })

  it('rejects unsupported current-page filters and mutations explicitly', async () => {
    const service = createProductLibraryRealService()
    await expect(
      service.list({
        view: 'all',
        keyword: '',
        platform: 'douyin',
        groupId: null,
        category: null,
        page: 1,
        pageSize: 20,
      }),
    ).rejects.toThrow('暂不支持平台或类目筛选')
    await expect(service.remove(['library-1'])).rejects.toThrow(
      '尚未接入正式接口',
    )
    expect(httpClient.get).not.toHaveBeenCalled()
  })
})
