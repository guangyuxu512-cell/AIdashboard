import { describe, expect, it } from 'vitest'
import { createProductLibraryMockService } from './product-library-mock-store'

describe('product library mock boundary', () => {
  it('uses twenty rows by default and keeps product ids as strings', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(page.items).toHaveLength(20)
    expect(page.total).toBeGreaterThan(20)
    expect(page.items.every((item) => typeof item.productId === 'string')).toBe(
      true,
    )
    expect(page.items.some((item) => item.currentPrice === null)).toBe(true)
  })

  it('filters groups and mutates only the explicit mock store', async () => {
    const service = createProductLibraryMockService()
    const initial = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    const group = await service.createGroup('演示新分组')
    expect(await service.moveToGroup([initial.items[0]!.id], group.id)).toBe(1)
    const filtered = await service.list({
      keyword: '',
      platform: null,
      groupId: group.id,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(filtered.items).toHaveLength(1)
    expect(filtered.items[0]?.groupName).toBe('演示新分组')
  })

  it('creates collection tasks through the shared mock-only entry', async () => {
    const service = createProductLibraryMockService()
    const page = await service.list({
      keyword: '',
      platform: null,
      groupId: null,
      category: null,
      page: 1,
      pageSize: 20,
    })
    expect(await service.recollect([page.items[1]!.id])).toBeGreaterThanOrEqual(
      0,
    )
  })
})
