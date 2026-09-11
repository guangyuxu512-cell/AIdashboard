import { describe, expect, it } from 'vitest'

import {
  toGenerationAssetDownloadRequests,
  type GenerationDownloadResult,
} from './download'

describe('generation asset download selection', () => {
  it('turns an explicit single selection into exactly that original-asset request', () => {
    const selected: GenerationDownloadResult = {
      id: 'item-main-2',
      slotIndex: 1,
      name: '日系主图2.png',
      status: 'SUCCESS',
      previewUrl: '/api/v1/assets/asset-main-2/content',
      thumbnailUrl: '/api/v1/assets/asset-main-2/thumbnail',
    }
    const unrelated: GenerationDownloadResult = {
      id: 'item-main-1',
      slotIndex: 0,
      name: '日系主图1.png',
      status: 'SUCCESS',
      previewUrl: '/api/v1/assets/asset-main-1/content',
    }

    expect(toGenerationAssetDownloadRequests([selected])).toEqual([
      {
        id: 'item-main-2',
        contentUrl: '/api/v1/assets/asset-main-2/content',
        filename: '日系主图2.png',
      },
    ])
    expect(toGenerationAssetDownloadRequests([selected])).not.toContainEqual(
      expect.objectContaining({ id: unrelated.id }),
    )
  })

  it('keeps group or batch selections scoped to successful original assets', () => {
    const results: GenerationDownloadResult[] = [
      {
        id: 'group-success',
        name: '组内成功.png',
        status: 'SUCCESS',
        previewUrl: '/api/v1/assets/group-success/content',
        thumbnailUrl: '/api/v1/assets/group-success/thumbnail',
        outputRole: 'MAIN_IMAGE',
        size: '1:1',
      },
      {
        id: 'group-failed',
        name: '组内失败.png',
        status: 'FAILED',
        previewUrl: '/api/v1/assets/group-failed/content',
        outputRole: 'MAIN_IMAGE',
        size: '1:1',
      },
      {
        id: 'batch-success',
        name: '其他组成功.png',
        status: 'SUCCESS',
        previewUrl: '/api/v1/assets/batch-success/content',
        outputRole: 'DETAIL_IMAGE',
        size: '1:1',
      },
    ]

    expect(toGenerationAssetDownloadRequests(results)).toEqual([
      {
        id: 'group-success',
        contentUrl: '/api/v1/assets/group-success/content',
        filename: '组内成功.png',
      },
      {
        id: 'batch-success',
        contentUrl: '/api/v1/assets/batch-success/content',
        filename: '其他组成功.png',
      },
    ])
  })
})
