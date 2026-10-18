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
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)
    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:protected-asset')
  })

  it('shows a protected thumbnail while an eager full image is still loading', async () => {
    let resolveThumbnail: ((blob: Blob) => void) | undefined
    let resolveFullImage: ((blob: Blob) => void) | undefined
    const thumbnail = new Promise<Blob>((resolve) => {
      resolveThumbnail = resolve
    })
    const fullImage = new Promise<Blob>((resolve) => {
      resolveFullImage = resolve
    })
    mocks.fetchAssetContent
      .mockImplementationOnce(() => thumbnail)
      .mockImplementationOnce(() => fullImage)
    vi.mocked(URL.createObjectURL)
      .mockReturnValueOnce('blob:thumbnail')
      .mockReturnValueOnce('blob:full-image')

    const wrapper = mount(AssetContentImage, {
      props: {
        src: '/api/v1/assets/asset-1/content',
        fallbackSrc: '/api/v1/assets/asset-1/thumbnail',
        alt: '慢响应图片',
        loading: 'eager',
        timeoutMs: 30_000,
      },
    })
    await flushPromises()

    expect(wrapper.attributes('data-state')).toBe('loading')
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(true)
    expect(mocks.fetchAssetContent).toHaveBeenNthCalledWith(
      1,
      '/api/v1/assets/asset-1/thumbnail',
      expect.any(AbortSignal),
    )
    expect(mocks.fetchAssetContent).toHaveBeenNthCalledWith(
      2,
      '/api/v1/assets/asset-1/content',
      expect.any(AbortSignal),
      { timeoutMs: 30_000 },
    )

    resolveThumbnail?.(new Blob(['thumbnail']))
    await flushPromises()
    expect(wrapper.attributes('data-state')).toBe('loading')
    expect(wrapper.attributes('data-source')).toBe('thumbnail')
    expect(wrapper.find('img').attributes('src')).toBe('blob:thumbnail')
    expect(wrapper.text()).toContain('正在加载原图')
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)

    resolveFullImage?.(new Blob(['full-image']))
    await flushPromises()
    expect(wrapper.attributes('data-state')).toBe('ready')
    expect(wrapper.attributes('data-source')).toBe('content')
    expect(wrapper.find('img').attributes('src')).toBe('blob:full-image')
    expect(wrapper.text()).not.toContain('正在加载原图')
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:thumbnail')
  })

  it('replaces a failed full image with an explicit retry instead of leaving the thumbnail as success', async () => {
    mocks.fetchAssetContent
      .mockResolvedValueOnce(new Blob(['thumbnail']))
      .mockRejectedValueOnce(new Error('完整图片读取失败'))
      .mockResolvedValueOnce(new Blob(['retry-thumbnail']))
      .mockResolvedValueOnce(new Blob(['full-image']))
    vi.mocked(URL.createObjectURL)
      .mockReturnValueOnce('blob:thumbnail')
      .mockReturnValueOnce('blob:retry-thumbnail')
      .mockReturnValueOnce('blob:full-image')

    const wrapper = mount(AssetContentImage, {
      props: {
        src: '/api/v1/assets/asset-1/content',
        fallbackSrc: '/api/v1/assets/asset-1/thumbnail',
        alt: '失败图片',
        loading: 'eager',
        interactive: true,
      },
    })
    await flushPromises()

    expect(wrapper.attributes('data-state')).toBe('error')
    expect(wrapper.attributes('data-source')).toBe('none')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)
    const retry = wrapper.get('button[aria-label="重新加载图片：失败图片"]')
    await retry.trigger('click')
    await flushPromises()

    expect(mocks.fetchAssetContent).toHaveBeenCalledTimes(4)
    expect(wrapper.emitted('activate')).toBeUndefined()
    expect(wrapper.attributes('data-state')).toBe('ready')
    expect(wrapper.attributes('data-source')).toBe('content')
    expect(wrapper.find('img').attributes('src')).toBe('blob:full-image')
  })

  it('keeps mock data urls local without issuing a request', async () => {
    const wrapper = mount(AssetContentImage, {
      props: { src: 'data:image/png;base64,AA==', alt: 'Mock图片' },
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).not.toHaveBeenCalled()
    expect(wrapper.find('img').attributes('src')).toBe(
      'data:image/png;base64,AA==',
    )
  })

  it('exposes an opt-in accessible activation surface for image previews', async () => {
    const wrapper = mount(AssetContentImage, {
      props: {
        src: 'data:image/png;base64,AA==',
        alt: '可预览图片',
        interactive: true,
      },
    })
    await flushPromises()

    expect(wrapper.attributes('role')).toBe('button')
    expect(wrapper.attributes('aria-label')).toBe('预览 可预览图片')
    await wrapper.trigger('click')
    expect(wrapper.emitted('activate')).toEqual([[]])
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

    const wrapper = mount(AssetContentImage, {
      props: { src: '/api/v1/assets/asset-1/thumbnail', alt: '延迟图片' },
    })
    await flushPromises()
    expect(mocks.fetchAssetContent).not.toHaveBeenCalled()
    expect(wrapper.attributes('data-state')).toBe('idle')
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(true)

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

  it('does not add an intrinsic grid placeholder for ready or empty direct sources', async () => {
    const wrapper = mount(AssetContentImage, {
      props: { src: 'data:image/svg+xml,<svg/>', alt: '竖图', loading: 'eager' },
    })
    expect(wrapper.attributes('data-state')).toBe('ready')
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)
    await wrapper.setProps({ src: '' })
    expect(wrapper.attributes('data-state')).toBe('empty')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.asset-content-image__placeholder').exists()).toBe(false)
    wrapper.unmount()
  })
})
