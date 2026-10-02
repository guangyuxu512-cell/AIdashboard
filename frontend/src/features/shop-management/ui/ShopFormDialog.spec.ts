import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { mapShopUpdateInput } from '@/entities/shop/api/shop-mapper'
import ShopFormDialog from './ShopFormDialog.vue'
import type { ShopFormViewModel } from '../model/types'

describe('ShopFormDialog simple collection flow', () => {
  it.each(['create', 'edit'] as const)(
    'omits operating date in %s without submitting a null reset',
    async (mode) => {
      const initialValue: ShopFormViewModel = {
        shopName: '已授权店铺',
        platform: 'douyin',
        platformShopId: null,
        enabled: true,
        ownerUserId: null,
        note: '仅修改备注',
      }
      const wrapper = mount(ShopFormDialog, {
        props: { show: false, mode, initialValue, ownerOptions: [] },
        global: {
          stubs: {
            FormDialog: { template: '<div><slot /></div>' },
            NForm: { template: '<form><slot /></form>' },
            NFormItem: {
              props: ['label'],
              template: '<label>{{ label }}<slot /></label>',
            },
            AppInput: true,
            AppSelect: true,
            AppSwitch: true,
          },
        },
      })
      await wrapper.setProps({ show: true })
      expect(wrapper.text()).not.toContain('经营日期')
      expect(wrapper.text()).not.toContain('经营起算日')
      await (wrapper.vm as unknown as { submit: () => Promise<void> }).submit()
      await flushPromises()
      const saved = wrapper.emitted('save')?.[0]?.[0] as ShopFormViewModel
      expect(saved).toEqual(initialValue)
      expect(saved).not.toHaveProperty('operatingStartDate')
      expect(
        mapShopUpdateInput({ ...saved, platform: 'douyin' }),
      ).not.toHaveProperty('operating_start_date')
      wrapper.unmount()
    },
  )
})
