import { describe, expect, it } from 'vitest'
import { createMockProductDataSource } from './product-data-mock'
import {
  createProductDataSource,
  PRODUCT_DATA_UNAVAILABLE,
} from './product-data-source'
import { emptyProductFilters, productPeriod } from '../model/query'
import { PRODUCT_ID_LENGTH_FIXTURE } from '../fixtures/product-id-lengths.fixture'
import type { ProductDataQuery } from '../model/types'

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
    expect(real).toMatchObject({ mode: 'real', available: false })
    await expect(real.list(query())).rejects.toThrow(PRODUCT_DATA_UNAVAILABLE)
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
        minExposure: 10000,
      },
    })
    expect(narrowed.page).toBeLessThan(9)
    expect(
      narrowed.items.every(
        (row) =>
          row.shopId === first.items[0]!.shopId &&
          Number(row.metrics.product_show_ucnt.value) >= 10000,
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
    expect(week.items[0]!.metrics.product_click_pay_ucnt_ratio).toEqual(
      one.items[0]!.metrics.product_click_pay_ucnt_ratio,
    )
    expect(one.items[1]!.metrics.product_show_ucnt).toMatchObject({
      state: 'available',
      value: '0',
    })
    expect(one.items[2]!.metrics.product_show_ucnt.state).toBe('missing')
    expect(one.items[3]!.metrics.receive_amt.state).toBe('null')
    expect(one.items[4]!.metrics.product_click_pay_ucnt_ratio.state).toBe(
      'invalid',
    )
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
    expect(source).toMatchObject({ mode: 'real', available: false })
    await expect(source.list(query())).rejects.toThrow(PRODUCT_DATA_UNAVAILABLE)
    await expect(source.groups('shop')).rejects.toThrow(
      PRODUCT_DATA_UNAVAILABLE,
    )
    await expect(
      source.saveGroup('shop', { id: null, name: '测试' }),
    ).rejects.toThrow(PRODUCT_DATA_UNAVAILABLE)
    await expect(source.assignGroup('shop', ['id'], null)).rejects.toThrow(
      PRODUCT_DATA_UNAVAILABLE,
    )
  })
})
