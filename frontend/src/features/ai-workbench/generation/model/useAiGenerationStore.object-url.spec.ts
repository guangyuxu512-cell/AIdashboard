import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { loadAiGenerationVisualMock } from './load-visual-mock'
import { useAiGenerationStore } from './useAiGenerationStore'
import type { GenerationSourceImageView } from './types'

function createStore() {
  const store = useAiGenerationStore()
  store.initializeVisualMock(loadAiGenerationVisualMock())
  return store
}

function localFile(name: string, content = 'image', lastModified = 1): File {
  return new File([content], name, {
    type: 'image/png',
    lastModified,
  })
}

function readyInstant(store: ReturnType<typeof useAiGenerationStore>): void {
  store.updateInstantPrompt('商品主体清晰')
}

describe('AI generation local Object URL lifecycle', () => {
  let objectUrlSequence = 0
  let createObjectUrl: ReturnType<typeof vi.fn>
  let revokeObjectUrl: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    objectUrlSequence = 0
    createObjectUrl = vi.fn(() => `blob:generation-${++objectUrlSequence}`)
    revokeObjectUrl = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: createObjectUrl,
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectUrl,
    })
  })

  afterEach(() => {
    Reflect.deleteProperty(URL, 'createObjectURL')
    Reflect.deleteProperty(URL, 'revokeObjectURL')
  })

  it('creates a managed URL for a local upload and revokes it after Draft removal', () => {
    const store = createStore()
    const file = localFile('product.png')

    store.addInstantUploadFiles('PRODUCT_IMAGES', [file])

    expect(createObjectUrl).toHaveBeenCalledOnce()
    expect(createObjectUrl).toHaveBeenCalledWith(file)
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual([
      expect.objectContaining({
        name: 'product.png',
        previewUrl: 'blob:generation-1',
        sourceType: 'LOCAL_UPLOAD',
        objectUrl: true,
      }),
    ])

    store.removeInstantSource(
      'PRODUCT_IMAGES',
      store.instantDraft.inputs.PRODUCT_IMAGES[0]!.id,
    )
    expect(revokeObjectUrl).toHaveBeenCalledOnce()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:generation-1')
  })

  it('does not create an unowned URL for an unavailable input slot', () => {
    const store = createStore()

    store.addInstantUploadFiles('REFERENCE_IMAGES', [
      localFile('reference.png'),
    ])

    expect(createObjectUrl).not.toHaveBeenCalled()
    expect(store.instantDraft.inputs.REFERENCE_IMAGES).toEqual([])
  })

  it('retains a Record lease when Draft removal releases its owner', () => {
    const store = createStore()
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    readyInstant(store)
    const draftImage = store.instantDraft.inputs.PRODUCT_IMAGES[0]!
    const record = store.generateInstant()!
    expect(record.detail.kind).toBe('INSTANT')
    if (record.detail.kind !== 'INSTANT') return
    const recordImage = record.detail.inputSlots[0]!.images[0]!

    expect(recordImage.previewUrl).toBe(draftImage.previewUrl)
    expect(recordImage).not.toBe(draftImage)
    store.removeInstantSource('PRODUCT_IMAGES', draftImage.id)

    expect(revokeObjectUrl).not.toHaveBeenCalled()
    expect(recordImage.previewUrl).toBe('blob:generation-1')

    store.$dispose()
    expect(revokeObjectUrl).toHaveBeenCalledOnce()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:generation-1')
  })

  it('keeps Record URLs alive across Draft reset and visual-mock reactivation', () => {
    const store = createStore()
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    readyInstant(store)
    const record = store.generateInstant()!

    store.resetInstantDraft()
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual([])
    expect(revokeObjectUrl).not.toHaveBeenCalled()

    store.setVisualMockActive(false)
    store.setVisualMockActive(true)
    expect(store.records.some((candidate) => candidate.id === record.id)).toBe(
      true,
    )
    expect(revokeObjectUrl).not.toHaveBeenCalled()

    store.$dispose()
    expect(revokeObjectUrl).toHaveBeenCalledTimes(1)
  })

  it('releases a removed style-reference Draft URL on STYLE to NORMAL cleanup', () => {
    const store = createStore()
    store.setInstantMode('STYLE_REPLICATION')
    store.addInstantUploadFiles('REFERENCE_IMAGES', [
      localFile('reference.png'),
    ])

    store.setInstantMode('NORMAL_GENERATION')

    expect(store.instantDraft.inputs.REFERENCE_IMAGES).toEqual([])
    expect(revokeObjectUrl).toHaveBeenCalledOnce()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:generation-1')
  })

  it('keeps a style-reference URL when its Record survives mode cleanup', () => {
    const store = createStore()
    store.setInstantMode('STYLE_REPLICATION')
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    store.addInstantUploadFiles('REFERENCE_IMAGES', [
      localFile('reference.png'),
    ])
    readyInstant(store)
    store.generateInstant()

    store.setInstantMode('NORMAL_GENERATION')

    expect(store.instantDraft.inputs.REFERENCE_IMAGES).toEqual([])
    expect(revokeObjectUrl).not.toHaveBeenCalled()
    store.removeInstantSource(
      'PRODUCT_IMAGES',
      store.instantDraft.inputs.PRODUCT_IMAGES[0]!.id,
    )
    expect(revokeObjectUrl).not.toHaveBeenCalled()

    store.$dispose()
    expect(revokeObjectUrl.mock.calls).toEqual([
      ['blob:generation-1'],
      ['blob:generation-2'],
    ])
  })

  it('releases the old URL and manages the new URL for same-ID replacement', () => {
    const store = createStore()
    const first = localFile('product.png', 'first', 10)
    const replacement = localFile('product.png', 'other', 10)

    store.addInstantUploadFiles('PRODUCT_IMAGES', [first])
    const sourceId = store.instantDraft.inputs.PRODUCT_IMAGES[0]!.id
    store.addInstantUploadFiles('PRODUCT_IMAGES', [replacement])

    expect(createObjectUrl).toHaveBeenCalledTimes(2)
    expect(revokeObjectUrl.mock.calls).toEqual([['blob:generation-1']])
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual([
      expect.objectContaining({
        id: sourceId,
        previewUrl: 'blob:generation-2',
      }),
    ])

    store.removeInstantSource('PRODUCT_IMAGES', sourceId)
    expect(revokeObjectUrl.mock.calls).toEqual([
      ['blob:generation-1'],
      ['blob:generation-2'],
    ])
  })

  it('does not revoke an old same-ID URL while a Record still owns it', () => {
    const store = createStore()
    const first = localFile('product.png', 'first', 10)
    const replacement = localFile('product.png', 'other', 10)
    store.addInstantUploadFiles('PRODUCT_IMAGES', [first])
    readyInstant(store)
    const record = store.generateInstant()!
    expect(record.detail.kind).toBe('INSTANT')
    if (record.detail.kind !== 'INSTANT') return

    store.addInstantUploadFiles('PRODUCT_IMAGES', [replacement])

    expect(revokeObjectUrl).not.toHaveBeenCalled()
    expect(record.detail.inputSlots[0]!.images[0]!.previewUrl).toBe(
      'blob:generation-1',
    )
    const replacementId = store.instantDraft.inputs.PRODUCT_IMAGES[0]!.id
    store.removeInstantSource('PRODUCT_IMAGES', replacementId)
    expect(revokeObjectUrl.mock.calls).toEqual([['blob:generation-2']])

    store.$dispose()
    expect(revokeObjectUrl.mock.calls).toEqual([
      ['blob:generation-2'],
      ['blob:generation-1'],
    ])
  })

  it('does not duplicate a Draft lease when the same managed source is assigned again', () => {
    const store = createStore()
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    const source = store.instantDraft.inputs.PRODUCT_IMAGES[0]!

    store.addInstantSources('PRODUCT_IMAGES', [{ ...source }])
    store.removeInstantSource('PRODUCT_IMAGES', source.id)

    expect(revokeObjectUrl).toHaveBeenCalledOnce()
    store.$dispose()
    expect(revokeObjectUrl).toHaveBeenCalledOnce()
  })

  it('never revokes remote, data, or unregistered blob URLs', () => {
    const store = createStore()
    const unmanagedSources: GenerationSourceImageView[] = [
      {
        id: 'remote-source',
        name: 'remote.png',
        previewUrl: 'https://cdn.example.com/remote.png',
        role: 'PRODUCT_SOURCE',
        sourceType: 'ASSET_LIBRARY',
      },
      {
        id: 'data-source',
        name: 'data.png',
        previewUrl: 'data:image/png;base64,AA==',
        role: 'PRODUCT_SOURCE',
        sourceType: 'LOCAL_UPLOAD',
        objectUrl: true,
      },
      {
        id: 'foreign-blob-source',
        name: 'foreign.png',
        previewUrl: 'blob:created-by-another-feature',
        role: 'PRODUCT_SOURCE',
        sourceType: 'LOCAL_UPLOAD',
        objectUrl: true,
      },
    ]
    store.addInstantSources('PRODUCT_IMAGES', unmanagedSources)

    unmanagedSources.forEach((source) =>
      store.removeInstantSource('PRODUCT_IMAGES', source.id),
    )
    store.$dispose()

    expect(createObjectUrl).not.toHaveBeenCalled()
    expect(revokeObjectUrl).not.toHaveBeenCalled()
  })

  it('disposes every remaining session URL once', () => {
    const store = createStore()
    store.setInstantMode('STYLE_REPLICATION')
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    store.addInstantUploadFiles('REFERENCE_IMAGES', [
      localFile('reference.png'),
    ])

    store.$dispose()

    expect(revokeObjectUrl.mock.calls).toEqual([
      ['blob:generation-1'],
      ['blob:generation-2'],
    ])
  })

  it('keeps each Record snapshot isolated from later Draft mutation', () => {
    const store = createStore()
    store.addInstantUploadFiles('PRODUCT_IMAGES', [localFile('product.png')])
    readyInstant(store)
    const draftImage = store.instantDraft.inputs.PRODUCT_IMAGES[0]!
    const record = store.generateInstant()!
    expect(record.detail.kind).toBe('INSTANT')
    if (record.detail.kind !== 'INSTANT') return
    const recordImage = record.detail.inputSlots[0]!.images[0]!

    draftImage.name = 'changed-after-generation.png'
    draftImage.previewUrl = 'https://example.com/changed.png'

    expect(recordImage).not.toBe(draftImage)
    expect(recordImage).toMatchObject({
      name: 'product.png',
      previewUrl: 'blob:generation-1',
    })

    store.$dispose()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:generation-1')
  })
})
