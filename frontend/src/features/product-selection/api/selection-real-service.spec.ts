import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import {
  createSelectionService,
  SELECTION_UNAVAILABLE,
} from './selection-service'
import { mapSelectionObservation } from './selection-real-service'
import type {
  SelectionObservationDto,
  SelectionMetricDto,
} from './selection-read-api'
import type { CandidateQuery } from '../model/contracts'

vi.mock('@/shared/api', () => ({ httpClient: { get: vi.fn() } }))

function observation(): SelectionObservationDto {
  const unavailable: SelectionMetricDto = {
    state: 'missing',
    retrieved_at: '2026-10-10T09:00:01Z',
    value_range: null,
  }
  return {
    observation_id: 'observation-id',
    last_run_id: null,
    candidate_id: 'candidate-id',
    product_id: '3769776708757094595',
    platform: 'douyin',
    request_shop_id: 'authorized-own-shop',
    request_shop_name: '自有请求店铺',
    source_scope_hash: 'scope-hash',
    source_context: {
      version: 1,
      platform: 'douyin',
      endpoint: 'product_rank/video_bring_good',
      business: {
        industry_id: '7',
        category_id: '1000009092,1000009142',
        brand_type: '-1',
        price_bin: '不限',
        search_info: '',
        rank_data_type: '1',
        date_type: '21',
        begin_date: '2026/10/02 00:00:00',
        end_date: '2026/10/08 00:00:00',
        activity_id: '',
      },
    },
    period_begin: '2026-10-02',
    period_end: '2026-10-08',
    title: '合成数据库响应',
    image_url: null,
    source_url: null,
    merchants: [{ platform_shop_id: '239490763', name: '实际商品商家' }],
    category_path: ['厨具', '厨房储物器具'],
    price_band: null,
    rank: 0,
    previous_rank: null,
    previous_checked_at: null,
    newly_on_ranking: null,
    first_seen_at: '2026-10-10T09:00:00Z',
    checked_at: '2026-10-10T09:00:00Z',
    metrics_retrieved_at: '2026-10-10T09:00:01Z',
    video_metric_ranges: {
      pay_amt: {
        ...unavailable,
        state: 'available',
        value_range: [
          { value: '10000000', value_type: 'int', unit: 'price' },
          { value: '25000000', value_type: 'int', unit: 'price' },
        ],
      },
      pay_combo_cnt: unavailable,
      product_click_cnt: {
        ...unavailable,
        state: 'available',
        value_range: [
          { value: '0', value_type: 'int', unit: 'number' },
          { value: '0', value_type: 'int', unit: 'number' },
        ],
      },
      video_cnt: unavailable,
    },
    first_on_shelf_date: '2025-08-17',
    bad_comment_rate_raw: '0.00205018686599039',
    bad_comment_rate_unit: 4,
    basic_info_retrieved_at: null,
    last_attempt_at: '2026-10-10T09:00:02Z',
    last_error_code: 'PLATFORM_TIMEOUT',
    last_error_stage: 'basic_info_request',
  }
}

const query: CandidateQuery = {
  page: 1,
  pageSize: 10,
  shopId: null,
  keyword: '',
  blocked: false,
  sortField: null,
  sortOrder: false,
}

describe('Real selection reads actual registered APIs, not mock execution', () => {
  beforeEach(() => vi.clearAllMocks())
  it('maps exact identity, original intervals, null, true zero and independent clocks', () => {
    const dto = observation()
    const result = mapSelectionObservation(dto)
    expect(result.productId).toBe('3769776708757094595')
    expect(result.merchant?.shopId).not.toBe(result.shopId)
    expect(result.negativeReviewRate).toBeNull()
    expect(result.negativeReviewRateRaw).toEqual({
      value: dto.bad_comment_rate_raw,
      unit: 4,
    })
    expect(result.userPaidAmountRange).toBe('10000000–25000000')
    expect(result.userPaidAmountUnit).toBeNull()
    expect(result.clicksRange).toBe('0–0')
    expect(result.soldUnitsRange).toBeNull()
    expect(result.rank).toBe(0)
    expect(result.discovery).toBe('unknown')
    expect(result.firstListed).toBeNull()
    expect(result.sourceContext.periodLabel).toBe('')
    expect(result.sourceContext.checkedAt).toBe(dto.checked_at)
    expect(result.metricsRetrievedAt).toBe(dto.metrics_retrieved_at)
    expect(result.basicInfoError).toBe('PLATFORM_TIMEOUT')
  })
  it('does not invent a unique merchant when the source has several', () => {
    const dto = observation()
    dto.merchants.push({ platform_shop_id: 'other', name: null })
    expect(mapSelectionObservation(dto).merchant).toBeNull()
  })
  it('queries database on list/detail/refresh; never invokes an execution API', async () => {
    const dto = observation()
    vi.mocked(httpClient.get)
      .mockResolvedValueOnce({
        data: { items: [dto], total: 1, page: 1, page_size: 10 },
      })
      .mockResolvedValueOnce({ data: dto })
    const real = await createSelectionService('real')
    const list = await real.candidates(query)
    expect(list.total).toBe(1)
    expect(await real.candidate(list.items[0]!.id)).toEqual(list.items[0])
    expect(httpClient.get).toHaveBeenCalledTimes(2)
    expect(httpClient.get).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/observations/observation-id',
    )
    await expect(real.collectBatch(['observation-id'])).rejects.toThrow(
      SELECTION_UNAVAILABLE,
    )
    expect(httpClient.get).toHaveBeenCalledTimes(2)
  })
  it('loads authorized real categories and keeps repeated all-node identities local to their paths', async () => {
    const real = await createSelectionService('real')
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        shop_id: 'authorized-own-shop',
        industry_id: '7',
        industry_name: '行业',
        selected_category_id: null,
        nodes: ['1001', '1002'].map((id) => ({
          category_id: id,
          name: id,
          children: [{ category_id: '0', name: '全部', children: [] }],
        })),
      },
    })
    const nodes = await real.categories('authorized-own-shop')
    expect(nodes[0]?.children?.[0]?.id).toBe('1001/0')
    expect(nodes[1]?.children?.[0]?.id).toBe('1002/0')
    expect(httpClient.get).toHaveBeenCalledExactlyOnceWith(
      '/api/v1/product-selection/categories',
      { params: { shop_id: 'authorized-own-shop' } },
    )
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: { shop_id: 'other-shop', nodes: [] },
    })
    await expect(real.categories('authorized-own-shop')).rejects.toThrow(
      '与当前请求店铺不一致',
    )
  })
  it('propagates failures, keeps legitimate empty results distinct, rejects unknown sorting before HTTP', async () => {
    const real = await createSelectionService('real')
    const failure = new Error('当前店铺授权已撤销')
    vi.mocked(httpClient.get)
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce({
        data: { items: [], total: 0, page: 1, page_size: 10 },
      })
    await expect(real.candidates(query)).rejects.toBe(failure)
    expect((await real.candidates(query)).items).toEqual([])
    await expect(
      real.candidates({
        ...query,
        sortField: 'negativeReviewRate',
        sortOrder: 'ascend',
      }),
    ).rejects.toThrow(SELECTION_UNAVAILABLE)
    expect(httpClient.get).toHaveBeenCalledTimes(2)
  })
})
