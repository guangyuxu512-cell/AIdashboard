import { beforeEach, describe, expect, it } from 'vitest'
import {
  createCollectionTaskMockService,
  enqueueCandidateCollectionTasks,
  resetCollectionTaskMockStore,
} from './collection-task-mock-store'

describe('collection task mock boundary', () => {
  beforeEach(() => resetCollectionTaskMockStore())

  it('validates duplicates only while creating and keeps queued tasks visible', async () => {
    const service = createCollectionTaskMockService()
    const receipt = await service.create({
      platform: 'douyin',
      inputMode: 'product',
      values: [
        '3832497447662387684',
        'https://item.example/998877665544332211',
      ],
    })
    expect(receipt.duplicates).toEqual([
      { value: '3832497447662387684', taskId: 'collection-demo-1' },
    ])
    expect(receipt.created).toHaveLength(1)
    expect(receipt.created[0]?.productId).toBe('998877665544332211')
    const page = await service.list({
      keyword: '998877665544332211',
      platform: 'douyin',
      status: 'queued',
      page: 1,
      pageSize: 20,
    })
    expect(page.items.map((item) => item.id)).toEqual([receipt.created[0]?.id])
  })

  it('shares candidate collection entries and keeps retry/cancel bounded by state', async () => {
    const service = createCollectionTaskMockService()
    expect(
      enqueueCandidateCollectionTasks([
        {
          candidateId: 'candidate-a',
          productId: '112233445566778899',
          title: '候选商品',
        },
      ]),
    ).toHaveLength(1)
    expect(
      enqueueCandidateCollectionTasks([
        {
          candidateId: 'candidate-a',
          productId: '112233445566778899',
          title: '候选商品',
        },
      ]),
    ).toHaveLength(0)
    const failed = await service.list({
      keyword: '',
      platform: null,
      status: 'failed',
      page: 1,
      pageSize: 20,
    })
    expect(await service.retry(failed.items.map((item) => item.id))).toBe(1)
    expect(await service.cancel(['collection-demo-2'])).toBe(1)
  })
})
