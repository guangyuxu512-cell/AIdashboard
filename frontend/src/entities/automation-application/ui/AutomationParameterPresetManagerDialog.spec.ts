import { flushPromises, shallowMount } from '@vue/test-utils'
import { NFormItem } from 'naive-ui'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

function mountDialog(
  options: {
    initialPresetId?: string | null
    schema?: typeof emptySchema | typeof configuredSchema
    show?: boolean
  } = {},
) {
  return shallowMount(AutomationParameterPresetManagerDialog, {
    props: {
      show: options.show ?? true,
      appId: application.app_id,
      schema: options.schema ?? emptySchema,
      applicationOptions: [application],
      allowSchemaConfiguration: true,
      initialPresetId: options.initialPresetId ?? null,
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
      .find((button) => button.text() === '管理字段')
    configure!.vm.$emit('click')
    await flushPromises()
    expect(wrapper.emitted('configureSchema')).toEqual([[application]])

    await wrapper.setProps({ schema: configuredSchema })
    await flushPromises()
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.text()).toContain('2 项当前参数')
    const fields = wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
    expect(fields.props('modelValue')).toEqual({ 页码: 1, 每页数量: 20 })
    expect(fields.props('layout')).toBe('compact')
    expect(fields.props('showRemove')).toBe(true)
  })

  it('keeps parameter selection in the current preset rather than changing its application schema', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '参数选择')
    const fields = wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
    fields.vm.$emit('remove', '每页数量')
    await flushPromises()

    expect(fields.props('modelValue')).toEqual({ 页码: 1 })
    const addParameter = wrapper
      .findAllComponents({ name: 'AppSelect' })
      .find((select) => select.props('placeholder') === '+ 添加参数')!
    addParameter.vm.$emit('update:modelValue', '每页数量')
    await flushPromises()
    expect(fields.props('modelValue')).toEqual({ 页码: 1, 每页数量: 20 })

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[0]![0].data.common_parameters).toEqual({
      页码: 1,
      每页数量: 20,
    })
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
    expect(
      wrapper
        .findAllComponents(NFormItem)
        .find((item) => item.props('label') === '预设名称')!
        .props('feedback'),
    ).toBe('当前团队中该应用的预设名称已存在')
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.emitted('update:show')).toBeUndefined()
  })

  it('keeps an unknown public parameter draft and identifies its source', async () => {
    mocks.save.mockRejectedValue(
      new ApiError({
        code: 'AUTOMATION_PARAMETER_PRESET_INVALID',
        message: '未知参数: 已移除字段',
      }),
    )
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '日常采集')
    wrapper
      .findAllComponents({ name: 'AutomationParameterFields' })[0]!
      .vm.$emit('update:modelValue', {
        页码: 1,
        每页数量: 20,
        已移除字段: '保留草稿',
      })
    await flushPromises()
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.text()).toContain(
      '公共参数包含服务端已不再定义的字段：已移除字段',
    )
    expect(
      wrapper
        .findAllComponents({ name: 'AutomationParameterFields' })[0]!
        .props('modelValue'),
    ).toMatchObject({ 已移除字段: '保留草稿' })
  })

  it('keeps an unknown shop override draft and returns to that shop', async () => {
    const presetWithRemovedShopField = {
      preset_id: 'preset-shop-field',
      app_id: application.app_id,
      name: '店铺差异预设',
      common_parameters: { 页码: 1, 每页数量: 20 },
      shop_overrides: { 'shop-a': { 已移除字段: '保留草稿' } },
      version: 2,
    }
    mocks.presets = {
      data: ref([presetWithRemovedShopField]),
      isPending: ref(false),
    }
    mocks.save.mockRejectedValue(
      new ApiError({
        code: 'AUTOMATION_PARAMETER_PRESET_INVALID',
        message: '未知参数: 已移除字段',
      }),
    )
    const wrapper = mountDialog({
      initialPresetId: presetWithRemovedShopField.preset_id,
      schema: configuredSchema,
    })
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.text()).toContain(
      '店铺“甲店”包含服务端已不再定义的字段：已移除字段',
    )
    expect(mocks.save.mock.calls[0]![0].data.shop_overrides).toMatchObject({
      'shop-a': { 已移除字段: '保留草稿' },
    })
  })

  it('keeps the draft visible and prevents saving when the shared schema API fails', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '日常采集')
    await wrapper.setProps({ schemaError: '应用参数配置暂时无法读取' })
    await flushPromises()

    expect(wrapper.text()).toContain(
      '参数定义读取失败：应用参数配置暂时无法读取',
    )
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    expect(wrapper.findComponent(FormDialog).props('submitDisabled')).toBe(true)
  })

  it('keeps an individual shop override in the main draft until the main form saves', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '店铺差异')
    wrapper
      .findAllComponents({ name: 'AppSelect' })
      .find((select) => select.props('placeholder') === '+ 添加店铺')!
      .vm.$emit('update:modelValue', 'shop-a')
    await flushPromises()

    wrapper
      .findComponent({ name: 'AutomationParameterPresetShopOverrideDialog' })
      .vm.$emit('confirm', { 页码: 0 })
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[0]![0].data.shop_overrides).toEqual({
      'shop-a': { 页码: 0 },
    })
  })

  it('does not add a new shop difference when the child editor is cancelled', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '店铺差异')
    wrapper
      .findAllComponents({ name: 'AppSelect' })
      .find((select) => select.props('placeholder') === '+ 添加店铺')!
      .vm.$emit('update:modelValue', 'shop-a')
    await flushPromises()

    wrapper
      .findComponent({ name: 'AutomationParameterPresetShopOverrideDialog' })
      .vm.$emit('update:show', false)
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(mocks.save.mock.calls[0]![0].data.shop_overrides).toEqual({})
  })

  it('uses the returned version for consecutive saves even if an older list response arrives', async () => {
    const initialPreset = {
      preset_id: 'preset-1',
      app_id: application.app_id,
      name: '日常采集',
      common_parameters: { 页码: 1, 每页数量: 20 },
      shop_overrides: {},
      version: 1,
    }
    const presets = ref([initialPreset])
    mocks.presets = { data: presets, isPending: ref(false) }
    mocks.save
      .mockResolvedValueOnce({ ...initialPreset, version: 2 })
      .mockResolvedValueOnce({ ...initialPreset, version: 3 })
    const wrapper = mountDialog({
      initialPresetId: initialPreset.preset_id,
      schema: configuredSchema,
    })
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[0]![0].data.expected_version).toBe(1)

    // A stale list must not reset the active editor to version 1.  The
    // mutation response remains the editor source of truth until the user
    // explicitly reopens/reloads it.
    presets.value = [initialPreset]
    await flushPromises()
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[1]![0].data.expected_version).toBe(2)
  })
})
