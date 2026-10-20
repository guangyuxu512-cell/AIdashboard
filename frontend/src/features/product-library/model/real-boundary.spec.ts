import { describe, expect, it } from 'vitest'
import { createCollectionTaskService } from '@/features/product-collection/api/collection-task-service'
import { createProductLibraryService } from '../api/product-library-service'

describe('product workspace Real boundary', () => {
  it('does not fall back to mock services in Real mode', async () => {
    const [tasks, products] = await Promise.all([
      createCollectionTaskService('real'),
      createProductLibraryService('real'),
    ])
    expect(tasks).toMatchObject({ available: false, mode: 'real' })
    expect(products).toMatchObject({ available: false, mode: 'real' })
    await expect(
      tasks.create({ platform: 'douyin', inputMode: 'product', values: ['1'] }),
    ).rejects.toThrow('尚未接入正式服务')
    await expect(products.groups()).rejects.toThrow('尚未接入')
  })
})
