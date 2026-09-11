import { flushPromises, shallowMount } from '@vue/test-utils'
import { NFormItem } from 'naive-ui'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ShopMultiSelector } from '@/entities/shop'
import { ApiError } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'

import AutomationParameterPresetManagerDialog from './AutomationParameterPresetManagerDialog.vue'

const mocks = vi.hoisted(() => ({
  copy: vi.fn(),
  error: vi.fn(),
  presets: null as unknown,
  save: vi.fn(),
  shops: null as unknown,
  success: vi.fn(),
}))

vi.mock('naive-ui', async (importOriginal) => ({
  ...(await importOriginal<typeof import('naive-ui')>()),
  useMessage: () => ({ error: mocks.error, success: mocks.success }),
}))

vi.mock('@/entities/shop', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/shop')>()),
  useShopSelectionOptionsQuery: () => mocks.shops,
}))

vi.mock('../api/queries', () => ({
  useAutomationParameterPresetsQuery: () => mocks.presets,
  useCopyAutomationParameterPresetMutation: () => ({
    isPending: ref(false),
    mutateAsync: mocks.copy,
  }),
  useSaveAutomationParameterPresetMutation: () => ({
    isPending: ref(false),
    mutateAsync: mocks.save,
  }),
}))

const application = { app_id: 'daily-collection', app_name: '日常采集' }
const emptySchema = { fields: [] }
const configuredSchema = {
  fields: [
    {
      name: '页码',
      label: '页码',
      type: 'number' as const,
      required: false,
      default_value: 1,
      options: [],
    },
    {
      name: '每页数量',
      label: '每页数量',
      type: 'number' as const,
      required: false,
      default_value: 20,
      options: [],
    },
  ],
}

function mountDialog(options: {
  schema?: typeof emptySchema | typeof configuredSchema
  show?: boolean
} = {}) {
  return shallowMount(AutomationParameterPresetManagerDialog, {
    props: {
      show: options.show ?? true,
      appId: application.app_id,
      schema: options.schema ?? emptySchema,
      applicationOptions: [application],
      allowSchemaConfiguration: true,
    },
    global: { renderStubDefaultSlot: true },
  })
}

beforeEach(() => {
  mocks.copy.mockReset()
  mocks.error.mockReset()
  mocks.save.mockReset()
  mocks.success.mockReset()
  mocks.save.mockResolvedValue({
    preset_id: 'preset-1',
    name: '日常采集',
    common_parameters: {},
    shop_overrides: {},
    version: 1,
  })
  mocks.presets = { data: ref([]), isPending: ref(false) }
  mocks.shops = {
    data: ref([
      { label: '甲店', value: 'shop-a' },
      { label: '乙店', value: 'shop-b' },
    ]),
    isPending: ref(false),
  }
})

describe('AutomationParameterPresetManagerDialog', () => {
  it('keeps a new preset draft while shared application fields are configured', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.text()).toContain('该应用尚未配置参数字段')
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '日常采集')
    await flushPromises()
    const configure = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '配置字段')
    configure!.vm.$emit('click')
    await flushPromises()
    expect(wrapper.emitted('configureSchema')).toEqual([[application]])

    await wrapper.setProps({ schema: configuredSchema })
    await flushPromises()
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.text()).toContain('当前应用已有 2 个共用参数字段')
    expect(
      wrapper
        .findAllComponents({ name: 'AutomationParameterFields' })[0]!
        .props('modelValue'),
    ).toEqual({ 页码: 1, 每页数量: 20 })
  })

  it('keeps the current draft and points a duplicate name failure at the name field', async () => {
    mocks.save.mockRejectedValue(
      new ApiError({
        code: 'AUTOMATION_PARAMETER_PRESET_CONFLICT',
        message: '当前团队中该应用的预设名称已存在',
      }),
    )
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '日常采集')
    await flushPromises()
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(mocks.save).toHaveBeenCalled()
    expect(wrapper.findAllComponents(NFormItem)[2]!.props('feedback')).toBe(
      '当前团队中该应用的预设名称已存在',
    )
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.emitted('update:show')).toBeUndefined()
  })

  it('keeps the draft visible and prevents saving when the shared schema API fails', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '日常采集')
    await wrapper.setProps({ schemaError: '应用参数配置暂时无法读取' })
    await flushPromises()

    expect(wrapper.text()).toContain('参数定义读取失败：应用参数配置暂时无法读取')
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.findComponent(FormDialog).props('submitDisabled')).toBe(true)
  })

  it('preserves explicit zero values in an individual shop override and restores inheritance', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(ShopMultiSelector).vm.$emit('update:modelValue', ['shop-a'])
    await flushPromises()

    const parameterFields = wrapper.findAllComponents({ name: 'AutomationParameterFields' })
    parameterFields[1]!.vm.$emit('update:modelValue', { 页码: 0, 每页数量: 20 })
    await flushPromises()
    expect(wrapper.text()).toContain('恢复继承 · 页码')
    wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '恢复继承 · 页码')!
      .vm.$emit('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('恢复继承 · 页码')
  })
})
