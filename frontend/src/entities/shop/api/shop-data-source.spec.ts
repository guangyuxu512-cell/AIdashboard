import { describe, expect, it } from 'vitest'

import { createMockShopDataSource } from './shop-data-source'
import { shopQueryKeys } from './shop-queries'

const emptyFilters = {
  platform: null,
  enabledStatus: null,
  sessionStatus: null,
  ownerUserId: null,
  keyword: '',
} as const

describe('shop query and mutation data source', () => {
  it('uses pagination values in a stable query key', () => {
    expect(
      shopQueryKeys.list({ page: 2, pageSize: 20, filters: emptyFilters }),
    ).toEqual([
      'shops',
      'list',
      { page: 2, pageSize: 20, filters: emptyFilters },
    ])
  })

  it('creates and updates one mock ViewModel through the same mutation boundary', async () => {
    const source = createMockShopDataSource()
    const created = await source.create({
      shopName: 'Mock Mutation Shop',
      platform: 'douyin',
      enabled: true,
      ownerUserId: null,
      note: '',
    })
    const updated = await source.update(created.shopId, {
      shopName: 'Mock Mutation Shop Updated',
      platform: 'douyin',
      enabled: false,
      ownerUserId: null,
      note: 'updated',
    })
    const page = await source.list({
      page: 1,
      pageSize: 10,
      filters: emptyFilters,
    })

    expect(updated.enabledStatus).toBe('disabled')
    expect(page.items[0]?.shopName).toBe('Mock Mutation Shop Updated')
    expect(page.total).toBe(9)
  })
})
