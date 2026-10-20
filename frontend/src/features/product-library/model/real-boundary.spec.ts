import { describe, expect, it } from 'vitest'
import { createCollectionTaskService } from '@/features/product-collection/api/collection-task-service'
import { createProductLibraryService } from '../api/product-library-service'

describe('product workspace Real boundary', () => {
  it('does not fall back to mock services in Real mode', async () => {
    const [tasks, products] = await Promise.all([
      createCollectionTaskService('real'),
      createProductLibraryService('real'),
    ])
    expect(tasks).toMatchObject({
      available: true,
      mode: 'real',
      supportsListFilters: false,
    })
    expect(products).toMatchObject({
      available: true,
      mode: 'real',
      capabilities: { edit: false, export: false, import: false },
    })
    await expect(
      products.saveEdit('product-id', {
        title: '不会保存',
        attributes: [],
        specDimensions: [],
        skus: [],
      }),
    ).rejects.toThrow('尚未接入正式接口')
  })
})
