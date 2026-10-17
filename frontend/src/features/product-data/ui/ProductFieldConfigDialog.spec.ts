import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'
import { AppCheckbox, AppDialog } from '@/shared/ui'
import {
  PRODUCT_DATA_FIELD_GROUPS,
  PRODUCT_DISPLAY_COLUMNS,
} from '../model/types'
import ProductFieldConfigDialog from './ProductFieldConfigDialog.vue'

const DialogStub = defineComponent({
  props: ['show', 'title', 'positiveDisabled'],
  emits: ['confirm', 'update:show'],
  template:
    '<section v-if="show"><slot /><slot name="footer-start" /></section>',
})
const TooltipStub = defineComponent({
  template: '<span><slot name="trigger" /><slot /></span>',
})

describe('product data field configuration', () => {
  it('uses the shared grouped whitelist and never exposes retired placeholders', () => {
    const wrapper = mount(ProductFieldConfigDialog, {
      props: { show: true, columns: ['shop'], userId: 'grouped-fields' },
      global: {
        stubs: { AppDialog: DialogStub, NTooltip: TooltipStub },
      },
    })
    try {
      const text = wrapper.text()
      for (const group of PRODUCT_DATA_FIELD_GROUPS)
        expect(text).toContain(group.label)
      expect(
        wrapper.findAllComponents(AppCheckbox).map((field) => field.text()),
      ).toEqual(PRODUCT_DISPLAY_COLUMNS.map(({ label }) => label))
      expect(text).not.toContain('结算金额')
      expect(text).not.toContain('退款金额（退款时间）')
      expect(text).not.toContain('实时可售库存')
      expect(text).toContain('商品信息 / ID · 固定左列；操作 · 固定右列')
      expect(text).toContain(`已显示 1 / ${PRODUCT_DISPLAY_COLUMNS.length}`)
    } finally {
      wrapper.unmount()
    }
  })

  it('saves checkbox choices in fixed business order regardless of click order', async () => {
    const wrapper = mount(ProductFieldConfigDialog, {
      props: {
        show: true,
        columns: ['trafficClickPayRate', 'shop', 'clickCount'],
        userId: 'fixed-field-order',
      },
      global: {
        stubs: { AppDialog: DialogStub, NTooltip: TooltipStub },
      },
    })
    try {
      const checkbox = (label: string) =>
        wrapper
          .findAllComponents(AppCheckbox)
          .find((field) => field.text() === label)!
      checkbox('曝光点击率').vm.$emit('update:modelValue', true)
      checkbox('支付金额').vm.$emit('update:modelValue', true)
      await wrapper.vm.$nextTick()
      wrapper.findComponent(AppDialog).vm.$emit('confirm')
      expect(wrapper.emitted('saved')?.[0]).toEqual([
        [
          'shop',
          'clickCount',
          'pay_amt',
          'trafficExposureClickRate',
          'trafficClickPayRate',
        ],
      ])
    } finally {
      wrapper.unmount()
      window.localStorage.clear()
    }
  })
})
