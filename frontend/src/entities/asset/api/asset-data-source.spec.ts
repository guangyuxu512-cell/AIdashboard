import { describe, expect, it } from 'vitest'

import { createAssetDataSource } from './asset-data-source'

describe('asset data source', () => {
  it('supports the minimal mock upload, search and delete lifecycle', async () => {
    const source = createAssetDataSource('mock')
    const initial = await source.list({ page: 1, pageSize: 20, search: '' })
    expect(initial.total).toBe(2)

    const uploaded = await source.upload(
      new File(['fixture'], '售后测试图.png', { type: 'image/png' }),
    )
    expect(uploaded.filename).toBe('售后测试图.png')

    const searched = await source.list({
      page: 1,
      pageSize: 20,
      search: '售后测试',
    })
    expect(searched.items.map((item) => item.assetId)).toEqual([
      uploaded.assetId,
    ])

    await source.remove(uploaded.assetId)
    const removed = await source.list({
      page: 1,
      pageSize: 20,
      search: '售后测试',
    })
    expect(removed.total).toBe(0)
  })
})
