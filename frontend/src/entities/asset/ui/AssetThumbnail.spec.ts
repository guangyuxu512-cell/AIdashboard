import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AssetContentImage from './AssetContentImage.vue'

const mocks = vi.hoisted(() => ({ fetchAssetContent: vi.fn() }))

vi.mock('../api/asset-api', () => ({
  fetchAssetContent: mocks.fetchAssetContent,
}))

describe('AssetContentImage', () => {
  beforeEach(() => {
    mocks.fetchAssetContent.mockReset()
    mocks.fetchAssetContent.mockResolvedValue(new Blob(['asset']))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:protected-asset'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    Reflect.deleteProperty(URL, 'createObjectURL')
    Reflect.deleteProperty(URL, 'revokeObjectURL')
  })

  it('uses an authenticated Blob request for protected thumbnail urls', async () => {
    const blob = new Blob(['asset'], { type: 'image/png' })
    mocks.fetchAssetContent.mockResolvedValue(blob)
    const createObjectUrl = vi.mocked(URL.createObjectURL)

    const wrapper = mount(AssetContentImage, {
      props: {
        src: '/api/v1/assets/asset-1/thumbnail',
        alt: '测试图片',
      },
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).toHaveBeenCalledWith(
      '/api/v1/assets/asset-1/thumbnail',
      expect.any(AbortSignal),
    )
    expect(createObjectUrl).toHaveBeenCalledWith(blob)
    expect(wrapper.find('img').attributes('src')).toBe('blob:protected-asset')
  })

  it('keeps mock data urls local without issuing a request', async () => {
    const wrapper = mount(AssetContentImage, {
      props: { src: 'data:image/png;base64,AA==', alt: 'Mock图片' },
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).not.toHaveBeenCalled()
    expect(wrapper.find('img').attributes('src')).toBe('data:image/png;base64,AA==')
  })

  it('defers a protected request until the image enters the viewport', async () => {
    let callback: ((entries: IntersectionObserverEntry[]) => void) | undefined
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(next: (entries: IntersectionObserverEntry[]) => void) {
          callback = next
        }

        disconnect() {}
        observe() {}
        unobserve() {}
        takeRecords() {
          return []
        }
        readonly root = null
        readonly rootMargin = '0px'
        readonly thresholds = []
      },
    )
    mocks.fetchAssetContent.mockResolvedValue(new Blob(['thumbnail']))

    mount(AssetContentImage, {
      props: { src: '/api/v1/assets/asset-1/thumbnail', alt: '延迟图片' },
    })
    await flushPromises()
    expect(mocks.fetchAssetContent).not.toHaveBeenCalled()

    callback?.([{ isIntersecting: true } as IntersectionObserverEntry])
    await flushPromises()
    expect(mocks.fetchAssetContent).toHaveBeenCalledTimes(1)
  })

  it('starts a new protected request when the source changes during a pending request', async () => {
    let resolveFirst: ((blob: Blob) => void) | undefined
    let resolveSecond: ((blob: Blob) => void) | undefined
    const first = new Promise<Blob>((resolve) => {
      resolveFirst = resolve
    })
    const second = new Promise<Blob>((resolve) => {
      resolveSecond = resolve
    })
    mocks.fetchAssetContent
      .mockImplementationOnce(() => first)
      .mockImplementationOnce(() => second)
    vi.mocked(URL.createObjectURL).mockReturnValue('blob:second-asset')

    const wrapper = mount(AssetContentImage, {
      props: {
        src: '/api/v1/assets/asset-first/content',
        alt: '第一张图片',
        loading: 'eager',
      },
    })
    await flushPromises()

    await wrapper.setProps({
      src: '/api/v1/assets/asset-second/content',
      alt: '第二张图片',
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).toHaveBeenNthCalledWith(
      1,
      '/api/v1/assets/asset-first/content',
      expect.any(AbortSignal),
    )
    expect(mocks.fetchAssetContent).toHaveBeenNthCalledWith(
      2,
      '/api/v1/assets/asset-second/content',
      expect.any(AbortSignal),
    )

    resolveFirst?.(new Blob(['first']))
    resolveSecond?.(new Blob(['second']))
    await flushPromises()

    expect(wrapper.find('img').attributes('src')).toBe('blob:second-asset')
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  })
})
