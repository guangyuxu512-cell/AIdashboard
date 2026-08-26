import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DataTable from '@/shared/components/DataTable.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'

import AssetMultiSelector from './AssetMultiSelector.vue'

const mocks = vi.hoisted(() => ({
  query: null as unknown,
  refetch: vi.fn(),
}))

vi.mock('@/entities/asset/api/asset-queries', () => ({
  useAssetListQuery: () => mocks.query,
}))

const rows = [
  {
    assetId: 'asset-1',
    mediaType: 'image',
    filename: 'test-01.jpg',
    contentType: 'image/jpeg',
    sizeBytes: 100,
    sizeDisplay: '100 B',
    sha256: 'a'.repeat(64),
    sourceType: 'upload',
    createdAt: '2026-08-26T00:00:00Z',
    createdAtDisplay: '2026-08-26 08:00',
    contentUrl: '/api/v1/assets/asset-1/content',
  },
  {
    assetId: 'asset-2',
    mediaType: 'image',
    filename: 'test-02.png',
    contentType: 'image/png',
    sizeBytes: 200,
    sizeDisplay: '200 B',
    sha256: 'b'.repeat(64),
    sourceType: 'upload',
    createdAt: '2026-08-26T00:01:00Z',
    createdAtDisplay: '2026-08-26 08:01',
    contentUrl: '/api/v1/assets/asset-2/content',
  },
]

beforeEach(() => {
  mocks.refetch.mockReset()
  mocks.query = {
    data: ref({ items: rows, total: 2, page: 1, pageSize: 100 }),
    isPending: ref(false),
    error: ref(null),
    refetch: mocks.refetch,
  }
})

describe('AssetMultiSelector', () => {
  it('defaults to no selected images and preserves the chosen order', async () => {
    const wrapper = shallowMount(AssetMultiSelector, {
      global: { renderStubDefaultSlot: true },
    })
    expect(wrapper.text()).toContain('未选择图片')

    await wrapper.findAllComponents({ name: 'AppButton' })[0]?.trigger('click')
    await flushPromises()
    const dialog = wrapper.findComponent(AppDialog)
    expect(dialog.props('show')).toBe(true)

    wrapper
      .findComponent(DataTable)
      .vm.$emit('update:checked-row-keys', ['asset-2', 'asset-1'])
    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [['asset-2', 'asset-1']],
    ])
  })

  it('can remove one selected image or clear the selection', async () => {
    const wrapper = shallowMount(AssetMultiSelector, {
      props: { modelValue: ['asset-1', 'asset-2'] },
      global: { renderStubDefaultSlot: true },
    })
    expect(wrapper.text()).toContain('已选择 2 张图片')

    const buttons = wrapper.findAllComponents({ name: 'AppButton' })
    await buttons.find((button) => button.text() === '移除')?.trigger('click')
    await buttons.find((button) => button.text() === '清空')?.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [['asset-2']],
      [[]],
    ])
  })
})
