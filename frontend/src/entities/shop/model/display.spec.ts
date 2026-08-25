import { describe, expect, it } from 'vitest'

import { SHOP_LIST_FIXTURE } from '../fixtures/shop-list.fixture'
import { getShopExecutionDeviceSummary } from './display'

describe('getShopExecutionDeviceSummary', () => {
  it('summarizes ordinary execution-qualified device bindings', () => {
    expect(getShopExecutionDeviceSummary(SHOP_LIST_FIXTURE[2])).toEqual({
      count: 3,
      label: '深圳-工作站-03 +2',
      names: ['深圳-工作站-03', '上海-直播机-02', '杭州-运营机-01'],
    })
  })

  it('uses the unassigned label when no device is bound', () => {
    expect(getShopExecutionDeviceSummary(SHOP_LIST_FIXTURE[3]).label).toBe(
      '未分配',
    )
  })
})
