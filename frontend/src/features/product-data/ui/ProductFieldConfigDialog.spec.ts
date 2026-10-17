import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppButton, AppCheckbox, AppDialog } from '@/shared/ui'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_DATA_FIELD_GROUPS,
  PRODUCT_DISPLAY_COLUMNS,
} from '../model/types'
import ProductFieldConfigDialog from './ProductFieldConfigDialog.vue'

const DialogStub = defineComponent({
  props: ['show', 'title', 'size', 'positiveDisabled'],
  emits: ['confirm', 'update:show'],
  template:
    '<section v-if="show"><slot /><slot name="footer-start" /></section>',
})
const TooltipStub = defineComponent({
  template: '<span><slot name="trigger" /><slot /></span>',
})
const global = { stubs: { AppDialog: DialogStub, NTooltip: TooltipStub } }

function selectedIds(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAll('[data-field-id]')
    .map((field) => field.attributes('data-field-id'))
}

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('product data field configuration', () => {
  it('keeps the four whitelist groups fixed and renders selected fields in saved order', () => {
    const wrapper = mount(ProductFieldConfigDialog, {
      props: {
        show: true,
        columns: ['trafficClickPayRate', 'shop'],
        userId: 'grouped-fields',
      },
      global,
    })
    try {
      const text = wrapper.text()
      for (const group of PRODUCT_DATA_FIELD_GROUPS)
        expect(text).toContain(group.label)
      expect(
        wrapper.findAllComponents(AppCheckbox).map((field) => field.text()),
      ).toEqual(PRODUCT_DISPLAY_COLUMNS.map(({ label }) => label))
      expect(selectedIds(wrapper)).toEqual(['trafficClickPayRate', 'shop'])
      expect(wrapper.findComponent(AppDialog).props('size')).toBe('lg')
      expect(text).not.toContain('结算金额')
      expect(text).not.toContain('退款金额（退款时间）')
      expect(text).not.toContain('实时可售库存')
      expect(text).toContain('商品信息 / ID · 固定左列；操作 · 固定右列')
      expect(text).toContain(`已显示 2 / ${PRODUCT_DISPLAY_COLUMNS.length}`)
      expect(text).toContain('拖动排序 · × 移除')
    } finally {
      wrapper.unmount()
    }
  })

  it('supports keyboard and drag reordering, appends new selections and saves one ordered preference', async () => {
    const wrapper = mount(ProductFieldConfigDialog, {
      props: {
        show: true,
        columns: ['trafficClickPayRate', 'shop', 'clickCount'],
        userId: 'ordered-fields',
      },
      global,
    })
    try {
      await wrapper
        .get('[data-field-id="shop"] .product-fields__drag-handle')
        .trigger('keydown', { key: 'ArrowUp' })
      const checkbox = (label: string) =>
        wrapper
          .findAllComponents(AppCheckbox)
          .find((field) => field.text() === label)!
      checkbox('曝光点击率').vm.$emit('update:modelValue', true)
      checkbox('支付金额').vm.$emit('update:modelValue', true)
      await wrapper.vm.$nextTick()

      const dataTransfer = {
        effectAllowed: 'none',
        dropEffect: 'none',
        setData: vi.fn(),
        getData: vi.fn(() => 'pay_amt'),
      }
      await wrapper
        .get('[data-field-id="pay_amt"]')
        .trigger('dragstart', { dataTransfer })
      await wrapper.get('[data-field-id="shop"]').trigger('dragover', {
        clientY: 1,
        dataTransfer,
      })
      await wrapper
        .get('[data-field-id="shop"]')
        .trigger('drop', { dataTransfer })
      expect(selectedIds(wrapper)).toEqual([
        'shop',
        'pay_amt',
        'trafficClickPayRate',
        'clickCount',
        'trafficExposureClickRate',
      ])

      wrapper.findComponent(AppDialog).vm.$emit('confirm')
      expect(wrapper.emitted('saved')?.[0]).toEqual([selectedIds(wrapper)])
      expect(
        JSON.parse(
          window.localStorage.getItem(
            'control-center.product-data.columns.v1.ordered-fields',
          )!,
        ),
      ).toEqual(selectedIds(wrapper))
    } finally {
      wrapper.unmount()
    }
  })

  it('keeps edits as a draft on cancel and restores the module default without clearing storage', async () => {
    const wrapper = mount(ProductFieldConfigDialog, {
      props: {
        show: true,
        columns: ['pay_cnt', 'shop'],
        userId: 'cancel-fields',
      },
      global,
    })
    try {
      await wrapper.get('[aria-label="移除店铺"]').trigger('click')
      expect(selectedIds(wrapper)).toEqual(['pay_cnt'])
      wrapper.findComponent(AppDialog).vm.$emit('update:show', false)
      await wrapper.setProps({ show: false })
      await wrapper.setProps({ show: true })
      expect(selectedIds(wrapper)).toEqual(['pay_cnt', 'shop'])
      expect(wrapper.emitted('saved')).toBeUndefined()
      expect(
        window.localStorage.getItem(
          'control-center.product-data.columns.v1.cancel-fields',
        ),
      ).toBeNull()

      await wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '恢复默认')!
        .trigger('click')
      expect(selectedIds(wrapper)).toEqual(DEFAULT_PRODUCT_COLUMNS)
    } finally {
      wrapper.unmount()
    }
  })
})
