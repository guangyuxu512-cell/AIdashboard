import { describe, expect, it } from 'vitest'

import { buildYingdaoApplicationSelectOptions } from './application-options'

describe('buildYingdaoApplicationSelectOptions', () => {
  it('adds stable ids only when application names collide', () => {
    expect(
      buildYingdaoApplicationSelectOptions([
        { app_id: 'app-a', app_name: '商品采集' },
        { app_id: 'app-b', app_name: '商品采集' },
        { app_id: 'app-c', app_name: '订单采集' },
      ]),
    ).toEqual([
      { label: '商品采集 · app-a', value: 'app-a' },
      { label: '商品采集 · app-b', value: 'app-b' },
      { label: '订单采集', value: 'app-c' },
    ])
  })
})
