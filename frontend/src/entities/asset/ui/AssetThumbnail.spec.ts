import { flushPromises, shallowMount } from '@vue/test-utils'
import { NImage } from 'naive-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AssetThumbnail from './AssetThumbnail.vue'

const mocks = vi.hoisted(() => ({ fetchAssetContent: vi.fn() }))

vi.mock('../api/asset-api', () => ({
  fetchAssetContent: mocks.fetchAssetContent,
}))

describe('AssetThumbnail', () => {
  beforeEach(() => {
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
    Reflect.deleteProperty(URL, 'createObjectURL')
    Reflect.deleteProperty(URL, 'revokeObjectURL')
  })

  it('uses an authenticated Blob request for backend content urls', async () => {
    const blob = new Blob(['asset'], { type: 'image/png' })
    mocks.fetchAssetContent.mockResolvedValue(blob)
    const createObjectUrl = vi.mocked(URL.createObjectURL)

    const wrapper = shallowMount(AssetThumbnail, {
      props: {
        src: '/api/v1/assets/asset-1/content',
        alt: '测试图片',
      },
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).toHaveBeenCalledWith(
      '/api/v1/assets/asset-1/content',
      expect.any(AbortSignal),
    )
    expect(createObjectUrl).toHaveBeenCalledWith(blob)
    expect(wrapper.findComponent(NImage).props('src')).toBe(
      'blob:protected-asset',
    )
  })

  it('keeps mock data urls local without issuing a request', async () => {
    const wrapper = shallowMount(AssetThumbnail, {
      props: { src: 'data:image/png;base64,AA==', alt: 'Mock图片' },
    })
    await flushPromises()

    expect(mocks.fetchAssetContent).not.toHaveBeenCalled()
    expect(wrapper.findComponent(NImage).props('src')).toBe(
      'data:image/png;base64,AA==',
    )
  })
})
