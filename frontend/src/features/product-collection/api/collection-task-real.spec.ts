import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import { createCollectionTaskRealService } from './collection-task-real'

vi.mock('@/shared/api', () => ({
  httpClient: { get: vi.fn(), post: vi.fn() },
}))

const detail = {
  request_id: 'request-1',
  submission_key: 'submission-1',
  source_kind: 'manual',
  target_group_id: null,
  status: 'partial',
  item_count: 2,
  pending_count: 0,
  running_count: 0,
  succeeded_count: 1,
  failed_count: 1,
  canceled_count: 0,
  cancel_requested_at: null,
  created_at: '2026-10-20T08:00:00+08:00',
  updated_at: '2026-10-20T08:10:00+08:00',
  finished_at: '2026-10-20T08:10:00+08:00',
  items: [
    {
      item_id: 'item-ok',
      candidate_id: null,
      platform: 'douyin',
      source_product_id: '10000001',
      collection_mode: 'auto_gateway',
      state: 'succeeded',
      library_product_id: 'library-1',
      attempt_count: 1,
      last_error_code: null,
      last_error_stage: null,
      last_error_message: null,
      created_at: '2026-10-20T08:00:00+08:00',
      updated_at: '2026-10-20T08:05:00+08:00',
      finished_at: '2026-10-20T08:05:00+08:00',
    },
    {
      item_id: 'item-failed',
      candidate_id: null,
      platform: 'douyin',
      source_product_id: '10000002',
      collection_mode: 'auto_gateway',
      state: 'failed',
      library_product_id: null,
      attempt_count: 1,
      last_error_code: 'DELIVERY_FAILED',
      last_error_stage: 'delivery',
      last_error_message: '派发失败',
      created_at: '2026-10-20T08:00:00+08:00',
      updated_at: '2026-10-20T08:10:00+08:00',
      finished_at: '2026-10-20T08:10:00+08:00',
    },
  ],
} as const

describe('collection task Real adapter', () => {
  beforeEach(() => vi.clearAllMocks())

  it('maps request summaries and refuses unsupported current-page filters', async () => {
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        items: [{ ...detail, items: null }],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const service = createCollectionTaskRealService()
    const page = await service.list({
      keyword: '',
      platform: null,
      status: null,
      page: 1,
      pageSize: 20,
    })
    expect(page.items[0]).toMatchObject({
      id: 'request-1',
      status: 'partial',
      progress: 100,
      failedCount: 1,
      items: null,
    })
    expect(httpClient.get).toHaveBeenCalledWith(
      '/api/v1/product-collection/requests',
      { params: { page: 1, page_size: 20 } },
    )
    await expect(
      service.list({
        keyword: '100',
        platform: null,
        status: null,
        page: 1,
        pageSize: 20,
      }),
    ).rejects.toThrow('暂不支持搜索')
  })

  it('creates one persisted request with a stable caller submission key', async () => {
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: {
        request_id: 'request-1',
        status: 'pending',
        item_count: 2,
        reused: false,
      },
    })
    vi.mocked(httpClient.get).mockResolvedValueOnce({ data: detail })
    const receipt = await createCollectionTaskRealService().create({
      platform: 'douyin',
      inputMode: 'product',
      values: ['10000001', '10000002'],
      submissionKey: '11111111-1111-4111-8111-111111111111',
    })
    expect(httpClient.post).toHaveBeenCalledWith(
      '/api/v1/product-collection/requests',
      {
        submission_key: '11111111-1111-4111-8111-111111111111',
        source: {
          kind: 'manual',
          targets: [
            { platform: 'douyin', product_id_or_supported_url: '10000001' },
            { platform: 'douyin', product_id_or_supported_url: '10000002' },
          ],
        },
      },
    )
    expect(receipt.created[0]?.items).toHaveLength(2)
  })

  it('does not expose unconnected PDD, Taobao, or shop-code paths as successful Real tasks', async () => {
    const service = createCollectionTaskRealService()
    await expect(
      service.create({
        platform: 'pdd',
        inputMode: 'product',
        values: ['10000001'],
        submissionKey: '22222222-2222-4222-8222-222222222222',
      }),
    ).rejects.toThrow('仅支持抖音商品')
    await expect(
      service.create({
        platform: 'taobao',
        inputMode: 'product',
        values: ['10000001'],
        submissionKey: '33333333-3333-4333-8333-333333333333',
      }),
    ).rejects.toThrow('仅支持抖音商品')
    await expect(
      service.create({
        platform: 'douyin',
        inputMode: 'shop-code',
        values: ['未接入店铺口令'],
        submissionKey: '44444444-4444-4444-8444-444444444444',
      }),
    ).rejects.toThrow('仅支持商品 ID')
    expect(httpClient.post).not.toHaveBeenCalled()
  })

  it('retries failed items only and exposes explicit recapture', async () => {
    vi.mocked(httpClient.get).mockResolvedValueOnce({ data: detail })
    vi.mocked(httpClient.post)
      .mockResolvedValueOnce({ data: detail })
      .mockResolvedValueOnce({ data: detail })
    const service = createCollectionTaskRealService()
    expect(await service.retry(['request-1'])).toBe(1)
    expect(httpClient.post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/product-collection/items/item-failed/retry',
    )
    await service.recaptureItem('item-ok')
    expect(httpClient.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/product-collection/items/item-ok/recapture',
    )
  })
})
