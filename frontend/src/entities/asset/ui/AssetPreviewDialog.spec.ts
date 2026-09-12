import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AssetPreviewDialog from './AssetPreviewDialog.vue'

const items = [
  {
    id: 'asset-1',
    name: '第一张.png',
    contentUrl: 'data:image/png;base64,AA==',
  },
  {
    id: 'asset-2',
    name: '第二张.png',
    contentUrl: 'data:image/png;base64,BB==',
  },
] as const

describe('AssetPreviewDialog', () => {
  it('uses authenticated-content compatible sources for zoomable navigation and download', async () => {
    const wrapper = mount(AssetPreviewDialog, {
      props: {
        show: true,
        items,
        selectedAssetId: 'asset-1',
      },
      global: { stubs: { teleport: true } },
    })

    expect(wrapper.text()).toContain('1 / 2 · 第一张.png')
    expect(
      wrapper.get('[aria-label="查看上一张图片"]').attributes('disabled'),
    ).toBeDefined()

    await wrapper.get('[aria-label="查看下一张图片"]').trigger('click')
    expect(wrapper.text()).toContain('2 / 2 · 第二张.png')

    await wrapper.get('[aria-label="放大预览"]').trigger('click')
    expect(
      wrapper.get('.asset-preview-dialog__image').attributes('style'),
    ).toContain('scale(1.25)')

    await wrapper.get('[aria-label="下载 第二张.png"]').trigger('click')
    expect(wrapper.emitted('download')).toEqual([[items[1]]])
  })
})
