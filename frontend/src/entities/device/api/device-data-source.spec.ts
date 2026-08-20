import { describe, expect, it } from 'vitest'

import { createMockDeviceDataSource } from './device-data-source'

const emptyFilters = {
  status: null,
  tag: null,
  workerVersion: null,
  capability: null,
  keyword: '',
} as const

describe('mock device data source office pagination', () => {
  it('returns exactly nine devices on the first office page', async () => {
    const source = createMockDeviceDataSource()
    const first = await source.list({ page: 1, pageSize: 9, filters: emptyFilters })
    const second = await source.list({ page: 2, pageSize: 9, filters: emptyFilters })
    expect(first.items).toHaveLength(9)
    expect(first.total).toBe(11)
    expect(second.items).toHaveLength(2)
  })
})
