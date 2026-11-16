import { describe, expect, it, vi } from 'vitest'

import { createGenerationObjectUrlRegistry } from './generation-object-url-registry'

function createRegistry() {
  let sequence = 0
  const createObjectUrl = vi.fn(() => `blob:generation-${++sequence}`)
  const revokeObjectUrl = vi.fn()
  const registry = createGenerationObjectUrlRegistry({
    createObjectUrl,
    revokeObjectUrl,
  })
  return { registry, createObjectUrl, revokeObjectUrl }
}

describe('GenerationObjectUrlRegistry', () => {
  it('registers a created URL with its first owner', () => {
    const { registry, createObjectUrl, revokeObjectUrl } = createRegistry()
    const file = new File(['image'], 'product.png', { type: 'image/png' })

    const url = registry.create(file, 'draft:PRODUCT_IMAGES:local-product')

    expect(url).toBe('blob:generation-1')
    expect(createObjectUrl).toHaveBeenCalledOnce()
    expect(createObjectUrl).toHaveBeenCalledWith(file)
    expect(registry.isManaged(url)).toBe(true)
    expect(registry.ownerCount(url)).toBe(1)
    expect(revokeObjectUrl).not.toHaveBeenCalled()
  })

  it('counts distinct Draft and Record owners without duplicate retain', () => {
    const { registry } = createRegistry()
    const url = registry.create(
      new Blob(['image']),
      'draft:PRODUCT_IMAGES:local-product',
    )

    expect(
      registry.retain(url, 'record:record-a:PRODUCT_IMAGES:local-product'),
    ).toBe(true)
    expect(
      registry.retain(url, 'record:record-a:PRODUCT_IMAGES:local-product'),
    ).toBe(true)
    expect(
      registry.retain(url, 'record:record-b:PRODUCT_IMAGES:local-product'),
    ).toBe(true)
    expect(registry.ownerCount(url)).toBe(3)
  })

  it('revokes only after the last owner releases the URL', () => {
    const { registry, revokeObjectUrl } = createRegistry()
    const url = registry.create(
      new Blob(['image']),
      'draft:PRODUCT_IMAGES:local-product',
    )
    registry.retain(url, 'record:record-a:PRODUCT_IMAGES:local-product')

    registry.release(url, 'draft:PRODUCT_IMAGES:local-product')
    expect(registry.ownerCount(url)).toBe(1)
    expect(revokeObjectUrl).not.toHaveBeenCalled()

    registry.release(url, 'record:record-a:PRODUCT_IMAGES:local-product')
    expect(registry.ownerCount(url)).toBe(0)
    expect(registry.isManaged(url)).toBe(false)
    expect(revokeObjectUrl).toHaveBeenCalledOnce()
    expect(revokeObjectUrl).toHaveBeenCalledWith(url)
  })

  it('ignores unknown owners and unmanaged URLs without duplicate revoke', () => {
    const { registry, revokeObjectUrl } = createRegistry()
    const url = registry.create(
      new Blob(['image']),
      'draft:PRODUCT_IMAGES:local-product',
    )

    expect(registry.release(url, 'record:missing')).toBe(false)
    expect(
      registry.release('https://cdn.example.com/product.png', 'draft'),
    ).toBe(false)
    expect(registry.retain('data:image/png;base64,AA==', 'record')).toBe(false)
    expect(revokeObjectUrl).not.toHaveBeenCalled()

    expect(registry.release(url, 'draft:PRODUCT_IMAGES:local-product')).toBe(
      true,
    )
    expect(registry.release(url, 'draft:PRODUCT_IMAGES:local-product')).toBe(
      false,
    )
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1)
  })

  it('disposes every remaining managed URL once and is idempotent', () => {
    const { registry, revokeObjectUrl } = createRegistry()
    const firstUrl = registry.create(new Blob(['first']), 'draft:first')
    const secondUrl = registry.create(new Blob(['second']), 'record:second')
    registry.retain(firstUrl, 'record:first')

    registry.disposeAll()
    registry.disposeAll()

    expect(revokeObjectUrl.mock.calls).toEqual([[firstUrl], [secondUrl]])
    expect(registry.ownerCount(firstUrl)).toBe(0)
    expect(registry.ownerCount(secondUrl)).toBe(0)
  })
})
