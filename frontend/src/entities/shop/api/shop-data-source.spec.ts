import { describe, expect, it } from 'vitest'

import { createMockShopDataSource } from './shop-data-source'
import { shopQueryKeys } from './shop-queries'

const emptyFilters = {
  enabledStatus: null,
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

  it('provides only enabled shops through the shared selector source', async () => {
    const source = createMockShopDataSource()
    await source.setEnabled('shop-fixture-001', false)

    const options = await source.listSelectionOptions()

    expect(options.some((option) => option.value === 'shop-fixture-001')).toBe(
      false,
    )
    expect(options.find((option) => option.value === 'shop-fixture-002')).toEqual(
      expect.objectContaining({ label: '海风家居生活馆' }),
    )
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
    expect(page.total).toBe(11)
  })

  it('persists enabled changes and soft-removes only the selected mock shop', async () => {
    const source = createMockShopDataSource()

    const disabled = await source.setEnabled('shop-fixture-001', false)
    expect(disabled.enabledStatus).toBe('disabled')
    expect((await source.get('shop-fixture-001')).enabled).toBe(false)

    await source.remove('shop-fixture-002')
    const page = await source.list({ page: 1, pageSize: 20, filters: emptyFilters })
    expect(page.total).toBe(9)
    expect(page.items.some((shop) => shop.shopId === 'shop-fixture-002')).toBe(false)
  })

  it('keeps identified identity read-only and manages binding enable state', async () => {
    const source = createMockShopDataSource()
    const identified = await source.get('shop-fixture-001')

    const updated = await source.update(identified.shopId, {
      shopName: '人工改名',
      platform: 'pdd',
      platformShopId: identified.platformShopId,
      enabled: identified.enabled,
      ownerUserId: identified.ownerUserId,
      note: identified.note,
    })
    await source.updateBinding(identified.shopId, {
      deviceId: 'device-fixture-001',
      enabled: false,
    })
    await source.createBinding(identified.shopId, {
      deviceId: 'device-fixture-002',
      enabled: true,
    })
    const rebound = await source.get(identified.shopId)

    expect(updated.shopName).toBe('星河服饰旗舰店')
    expect(updated.platform).toBe('douyin')
    expect(rebound.executionDeviceIds).toEqual(['device-fixture-002'])
    expect(
      rebound.deviceBindings?.find(
        (binding) => binding.deviceId === 'device-fixture-001',
      )?.enabled,
    ).toBe(false)
  })
})
