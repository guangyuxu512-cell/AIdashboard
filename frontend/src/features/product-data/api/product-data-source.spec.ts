import { describe, expect, it, vi } from 'vitest'
import { createMockProductDataSource } from './product-data-mock'
import { createProductDataSource } from './product-data-source'
import { PRODUCT_DATA_GROUPS_UNAVAILABLE } from './product-data-real'
import { emptyProductFilters, productPeriod } from '../model/query'
import { PRODUCT_ID_LENGTH_FIXTURE } from '../fixtures/product-id-lengths.fixture'
import { PRODUCT_RANGE_FILTERS } from '../model/metric-ranges'
import type { ProductDataQuery } from '../model/types'

vi.mock('@/shared/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api')>()),
  httpClient: {
    get: vi.fn(async () => {
      throw new Error('synthetic-api-unavailable')
    }),
  },
}))

function query(): ProductDataQuery {
  return {
    filters: emptyProductFilters(),
    period: { startDate: '2026-10-01', endDate: '2026-10-01' },
    page: 1,
    pageSize: 10,
    sort: null,
  }
}
describe('product data source boundaries', () => {
  it.each(PRODUCT_RANGE_FILTERS)(
    'filters the complete Mock metric set, including off-page records, before pagination: $id',
    async (field) => {
      const source = createMockProductDataSource(),
        params = query()
      const full = (await source.list({ ...params, pageSize: 100 })).items
      params.filters.metricRanges[field.id] = {
        choice: 'custom',
        min: field.percent ? 1 : 0,
        max: field.percent ? 30 : 100,
      }
      const expected = full.filter((row) => {
        const metric = row.metrics[field.id]
        return (
          metric.state === 'available' &&
          metric.value !== null &&
          Number(metric.value) >= (field.percent ? 0.01 : 0) &&
          Number(metric.value) < (field.percent ? 0.3 : 100)
        )
      })
      expect(expected.length).toBeGreaterThan(0)
      expect(expected.length).toBeLessThan(full.length)
      const filtered = await source.list({ ...params, page: 1, pageSize: 2 })
      expect(filtered.total).toBe(expected.length)
      expect(filtered.items).toEqual(expected.slice(0, 2))
      const second = await source.list({ ...params, page: 2, pageSize: 2 })
      expect(second.items).toEqual(expected.slice(2, 4))
    },
  )
  it('combines shop, identity, name, group, sale type, image-text carrier and a metric interval', async () => {
    const source = createMockProductDataSource(),
      params = query()
    const all = (await source.list({ ...params, pageSize: 100 })).items
    const target = all[15]!
    expect(target).toMatchObject({
      selling: 'cooperation',
      carrier: 'image-text',
    })
    const group = await source.saveGroup(target.shopId, {
      id: null,
      name: '组合筛选',
    })
    await source.assignGroup(target.shopId, [target.id], group.id)
    const result = await source.list({
      ...params,
      page: 2,
      filters: {
        ...params.filters,
        shopId: target.shopId,
        productId: target.productId,
        productName: '演示商品 16',
        groupId: group.id,
        selling: 'cooperation',
        carrier: 'image-text',
        metricRanges: {
          ...params.filters.metricRanges,
          clickCount: { choice: 'preset-3', min: null, max: null },
        },
      },
    })
    expect(result.total).toBe(1)
    expect(result.page).toBe(1)
    expect(result.items[0]!.id).toBe(target.id)
    expect((await source.list(params)).total).toBe(31)
    await expect(
      source.list({
        ...params,
        filters: {
          ...params.filters,
          metricRanges: {
            ...params.filters.metricRanges,
            netOrders: { choice: 'custom', min: -1, max: null },
          },
        },
      }),
    ).rejects.toThrow('负数')
    expect(
      all.every(
        (row) =>
          row.metrics.refund_cnt.state === 'missing' &&
          row.metrics.stock_cnt.state === 'missing',
      ),
    ).toBe(true)
    expect(all[0]!.metrics.netOrders.value).toBe('2')
    expect(all[0]!.metrics.refundRelatedOrders.value).toBe('2')
    expect(all[0]!.metrics.pay_cnt.value).toBe('3')
  })
  it('limits mixed-length ID fixtures to the explicit Mock preview and preserves exact strings', async () => {
    const preview = await createProductDataSource('mock', 'mixed-ids')
    const ids = (await preview.list(query())).items
      .slice(0, 3)
      .map((row) => row.productId)
    expect(ids).toEqual(PRODUCT_ID_LENGTH_FIXTURE)
    expect(ids.map((id) => id.length)).toEqual([2, 18, 98])
    const standard = await createProductDataSource('mock')
    expect((await standard.list(query())).items[0]!.productId).toBe(
      '9000000000000000001',
    )
    const real = await createProductDataSource('real', 'mixed-ids')
    expect(real).toMatchObject({
      mode: 'real',
      available: true,
      groupsAvailable: false,
    })
    await expect(real.list(query())).rejects.toThrow(
      'synthetic-api-unavailable',
    )
  })
  it('limits the successful initial-empty fixture to its explicit Mock preview', async () => {
    const preview = await createProductDataSource('mock', 'empty-success')
    await expect(preview.list(query())).resolves.toMatchObject({
      items: [],
      total: 0,
      page: 1,
    })
    const standard = await createProductDataSource('mock')
    await expect(standard.list(query())).resolves.toMatchObject({ total: 31 })
  })
  it('filters and sorts the entire result before pagination, keeping missing last in either direction', async () => {
    const source = createMockProductDataSource()
    const params = query()
    const first = await source.list(params)
    expect(first.total).toBe(31)
    const sorted = await source.list({
      ...params,
      sort: { field: 'product_show_ucnt', direction: 'desc' },
    })
    expect(sorted.items[0]!.id).toBe('product-data-demo-30')
    expect(first.items.some((row) => row.id === sorted.items[0]!.id)).toBe(
      false,
    )
    for (const direction of ['asc', 'desc'] as const) {
      const all = await source.list({
        ...params,
        pageSize: 100,
        sort: { field: 'product_show_ucnt', direction },
      })
      expect(all.items.at(-1)!.metrics.product_show_ucnt.state).toBe('missing')
    }
    const canonicalRate = await source.list({
      ...params,
      pageSize: 100,
      sort: { field: 'exposureClickRate', direction: 'desc' },
    })
    const trafficAlias = await source.list({
      ...params,
      pageSize: 100,
      sort: { field: 'trafficExposureClickRate', direction: 'desc' },
    })
    expect(trafficAlias.items.map(({ id }) => id)).toEqual(
      canonicalRate.items.map(({ id }) => id),
    )
    const byId = await source.list({
      ...params,
      filters: {
        ...params.filters,
        productId: first.items[0]!.productId,
        productName: '随行杯',
      },
    })
    expect(byId.total).toBe(1)
    const narrowed = await source.list({
      ...params,
      page: 9,
      filters: {
        ...params.filters,
        shopId: first.items[0]!.shopId,
        metricRanges: {
          ...params.filters.metricRanges,
          exposureCount: { choice: 'custom', min: 10000, max: null },
        },
      },
    })
    expect(narrowed.page).toBeLessThan(9)
    expect(
      narrowed.items.every(
        (row) =>
          row.shopId === first.items[0]!.shopId &&
          Number(row.metrics.exposureCount.value) >= 10000,
      ),
    ).toBe(true)
  })
  it('uses the chosen period and distinguishes zero, missing, null and invalid without averaging ratios', async () => {
    const source = createMockProductDataSource()
    const one = await source.list(query())
    const week = await source.list({
      ...query(),
      period: { startDate: '2026-10-01', endDate: '2026-10-07' },
    })
    expect(Number(week.items[0]!.metrics.receive_amt.value)).toBeCloseTo(
      Number(one.items[0]!.metrics.receive_amt.value) * 7,
    )
    expect(week.items[0]!.metrics.clickPayRate).toEqual(
      one.items[0]!.metrics.clickPayRate,
    )
    expect(one.items[1]!.metrics.product_show_ucnt).toMatchObject({
      state: 'available',
      value: '0',
    })
    expect(one.items[2]!.metrics.product_show_ucnt.state).toBe('missing')
    expect(one.items[3]!.metrics.receive_amt.state).toBe('null')
    expect(one.items[4]!.metrics.clickPayRate.state).toBe('invalid')
    expect(
      productPeriod(
        { ...emptyProductFilters(), datePreset: 'last7Days' },
        new Date('2026-10-14T17:00:00Z'),
      ),
    ).toEqual({ startDate: '2026-10-08', endDate: '2026-10-14' })
    expect(() =>
      productPeriod({ ...emptyProductFilters(), datePreset: 'custom' }),
    ).toThrow('请选择统计日期')
  })
  it('creates groups from zero, isolates names by shop, assigns/removes and deletes only memberships', async () => {
    const source = createMockProductDataSource()
    const rows = (await source.list({ ...query(), pageSize: 100 })).items
    const a = rows[0]!,
      b = rows[30]!
    expect(await source.groups(a.shopId)).toEqual([])
    const group = await source.saveGroup(a.shopId, { id: null, name: '出单款' })
    const other = await source.saveGroup(b.shopId, { id: null, name: '出单款' })
    await source.assignGroup(a.shopId, [a.id], group.id)
    expect(await source.groups(a.shopId)).toEqual([
      { ...group, productCount: 1 },
    ])
    await expect(
      source.assignGroup(a.shopId, [a.id, b.id], group.id),
    ).rejects.toThrow('同一店铺')
    await expect(
      source.assignGroup(a.shopId, [a.id], other.id),
    ).rejects.toThrow('不属于')
    await expect(source.deleteGroup(b.shopId, group.id)).rejects.toThrow(
      '不属于',
    )
    const renamed = await source.saveGroup(a.shopId, {
      id: group.id,
      name: '福利款',
    })
    expect(renamed.name).toBe('福利款')
    await expect(
      source.saveGroup(a.shopId, { id: null, name: '福利款' }),
    ).rejects.toThrow('同名')
    await source.assignGroup(a.shopId, [a.id], null)
    await source.assignGroup(a.shopId, [a.id], group.id)
    await source.deleteGroup(a.shopId, group.id)
    const after = await source.list({ ...query(), pageSize: 100 })
    expect(after.total).toBe(rows.length)
    expect(after.items[0]!.groupId).toBeNull()
    expect(after.items[0]!.metrics).toEqual(a.metrics)
    expect(await source.groups(b.shopId)).toEqual([other])
  })
  it('keeps failure recoverable and never falls back in Real', async () => {
    const mock = createMockProductDataSource({ failOnce: 'list' })
    await expect(mock.list(query())).rejects.toThrow('请重试')
    expect((await mock.list(query())).total).toBe(31)
    const source = await createProductDataSource('real', 'query-error')
    expect(source).toMatchObject({
      mode: 'real',
      available: true,
      groupsAvailable: false,
    })
    await expect(source.list(query())).rejects.toThrow(
      'synthetic-api-unavailable',
    )
    await expect(source.groups('shop')).rejects.toThrow(
      PRODUCT_DATA_GROUPS_UNAVAILABLE,
    )
    await expect(
      source.saveGroup('shop', { id: null, name: '测试' }),
    ).rejects.toThrow(PRODUCT_DATA_GROUPS_UNAVAILABLE)
    await expect(source.assignGroup('shop', ['id'], null)).rejects.toThrow(
      PRODUCT_DATA_GROUPS_UNAVAILABLE,
    )
  })
})
