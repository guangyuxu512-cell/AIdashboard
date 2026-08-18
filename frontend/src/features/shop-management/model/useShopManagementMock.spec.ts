import { describe, expect, it } from 'vitest'

import { useShopManagementMock } from './useShopManagementMock'

describe('useShopManagementMock', () => {
  it('filters fixture rows only after query and resets them', () => {
    const management = useShopManagementMock()

    management.filterDraft.value.platform = 'douyin'
    expect(management.filteredShops.value).toHaveLength(8)

    management.query()
    expect(management.filteredShops.value).toHaveLength(2)
    expect(
      management.filteredShops.value.every(
        (shop) => shop.platform === 'douyin',
      ),
    ).toBe(true)

    management.resetFilters()
    expect(management.filteredShops.value).toHaveLength(8)
  })

  it('creates a local view-model row without backend data', () => {
    const management = useShopManagementMock()

    management.openCreate()
    management.saveShop({
      shopName: 'Fixture 新店',
      platform: 'taobao',
      ownerName: '测试负责人',
      executionDeviceId: null,
      note: '仅用于前端测试',
    })

    expect(management.statistics.value.total).toBe(9)
    expect(management.filteredShops.value[0]).toMatchObject({
      shopName: 'Fixture 新店',
      sessionStatus: 'not_configured',
      automationStatus: 'idle',
      accountConfigurationStatus: 'not_configured',
    })
  })
})
