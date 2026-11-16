import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { MaterialAssetReference } from '../model/types'

import MaterialAssetGrid from './MaterialAssetGrid.vue'

const asset: MaterialAssetReference = {
  assetId: 'asset-1',
  name: '正面.jpg',
  mediaType: 'image/jpeg',
  sourceType: 'MATERIAL_IMPORT',
  role: 'PRODUCT_SOURCE',
  previewUrl: 'data:image/jpeg;base64,AA==',
}

describe('MaterialAssetGrid', () => {
  it('renders no card checkbox and opens the inspector in normal mode', async () => {
    const wrapper = shallowMount(MaterialAssetGrid, {
      props: {
        assets: [asset],
        selectedAssetId: null,
        selectedAssetIds: [],
        selectionMode: false,
      },
    })

    expect(wrapper.find('.material-asset-card__checkbox').exists()).toBe(false)
    expect(wrapper.find('[role="checkbox"]').exists()).toBe(false)

    await wrapper.get('button.material-asset-card').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['asset-1']])
    expect(wrapper.emitted('update:selected')).toBeUndefined()
  })

  it('toggles the whole-card selected state without opening the inspector', async () => {
    const wrapper = shallowMount(MaterialAssetGrid, {
      props: {
        assets: [asset],
        selectedAssetId: null,
        selectedAssetIds: [],
        selectionMode: true,
      },
    })
    const card = wrapper.get('button.material-asset-card')

    await card.trigger('click')
    expect(wrapper.emitted('update:selected')).toEqual([['asset-1', true]])
    expect(wrapper.emitted('select')).toBeUndefined()

    await wrapper.setProps({ selectedAssetIds: ['asset-1'] })
    expect(card.classes()).toContain('material-asset-card--selected')
    expect(card.attributes('aria-pressed')).toBe('true')

    await card.trigger('click')
    expect(wrapper.emitted('update:selected')).toEqual([
      ['asset-1', true],
      ['asset-1', false],
    ])
  })
})
