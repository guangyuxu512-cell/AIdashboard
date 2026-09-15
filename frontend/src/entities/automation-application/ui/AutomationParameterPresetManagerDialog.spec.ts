import { flushPromises, shallowMount } from '@vue/test-utils'
import { NFormItem } from 'naive-ui'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AutomationInputSchemaDto } from '../api/contracts'

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
const expandedSchema = {
  fields: [
    ...configuredSchema.fields,
    {
      name: '最大页数',
      label: '最大页数',
      type: 'number' as const,
      required: false,
      default_value: 100,
      options: [],
    },
  ],
}

function mountDialog(
  options: {
    appId?: string | null
    applicationOptions?: typeof application[]
    applicationOptionsError?: string | null
    applicationOptionsLoading?: boolean
    deviceId?: string | null
    initialPresetId?: string | null
    schema?: typeof emptySchema | typeof configuredSchema | typeof expandedSchema
    show?: boolean
  } = {},
) {
  return shallowMount(AutomationParameterPresetManagerDialog, {
    props: {
      show: options.show ?? true,
      appId:
        options.appId === undefined ? application.app_id : options.appId,
      schema: options.schema ?? emptySchema,
      applicationOptions: options.applicationOptions ?? [application],
      applicationOptionsError: options.applicationOptionsError ?? null,
      applicationOptionsLoading: options.applicationOptionsLoading ?? false,
      deviceId: options.deviceId ?? null,
      deviceOptions: [
        { label: '设备一', value: 'device-1' },
        { label: '设备二', value: 'device-2' },
      ],
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
    input_schema: emptySchema,
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
  it('keeps device filtering local and preserves the draft when the application remains available', async () => {
    const wrapper = mountDialog({
      deviceId: 'device-1',
      schema: configuredSchema,
    })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '设备共享配置')
    wrapper
      .findAllComponents({ name: 'AutomationParameterFields' })[0]!
      .vm.$emit('update:modelValue', { 页码: 2 })

    const deviceSelect = wrapper
      .findAllComponents(AppSelect)
      .find((select) => select.props('placeholder') === '全部设备')!
    deviceSelect.vm.$emit('update:modelValue', 'device-2')
    await wrapper.setProps({ deviceId: 'device-2' })
    await flushPromises()

    expect(wrapper.emitted('update:deviceId')).toEqual([['device-2']])
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe(
      '设备共享配置',
    )
    expect(
      wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
        .props('modelValue'),
    ).toEqual({ 页码: 2 })
  })

  it('clears an application that is unavailable on the selected device and explains why', async () => {
    const wrapper = mountDialog({
      deviceId: 'device-1',
      schema: configuredSchema,
    })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '错误设备配置')

    await wrapper.setProps({
      deviceId: 'device-2',
      applicationOptions: [],
    })
    await flushPromises()
    expect(wrapper.emitted('update:appId')).toEqual([[null]])
    await wrapper.setProps({ appId: null })
    await flushPromises()

    expect(wrapper.text()).toContain(
      '原应用在所选设备上不可用，已清除应用选择和对应参数草稿。',
    )
    expect(wrapper.text()).toContain('该设备当前没有可用的影刀应用。')
  })

  it('asks for an application before showing parameter-definition loading', async () => {
    const wrapper = mountDialog({
      appId: null,
      applicationOptionsLoading: false,
      schema: emptySchema,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('请先选择应用。')
    expect(wrapper.text()).not.toContain('正在读取参数定义。')
    for (const placeholder of ['全部设备', '选择影刀应用']) {
      const select = wrapper
        .findAllComponents(AppSelect)
        .find((item) => item.props('placeholder') === placeholder)!
      expect(select.props('to')).toBe('#app-overlay-host')
    }
  })

  it('does not clear the current application when device applications fail to load', async () => {
    const wrapper = mountDialog({
      applicationOptions: [],
      applicationOptionsError: '无权读取设备应用',
      deviceId: 'device-2',
      schema: configuredSchema,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('应用列表读取失败：无权读取设备应用')
    expect(wrapper.emitted('update:appId')).toBeUndefined()
  })

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
    expect(wrapper.emitted('configureSchema')).toEqual([[application, emptySchema]])

    await wrapper.setProps({ schema: configuredSchema })
    await flushPromises()
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('日常采集')
    // Returning from global/template editing alone cannot mutate this draft;
    // the parent must pass an explicit preset-local schema confirmation.
    expect(wrapper.text()).toContain('该应用尚未配置参数字段')
    ;(wrapper.vm as unknown as {
      applyInputSchema: (schema: AutomationInputSchemaDto) => void
    }).applyInputSchema(configuredSchema)
    await flushPromises()
    expect(wrapper.text()).toContain('0 项当前参数')
    const fields = wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
    expect(fields.props('modelValue')).toEqual({})
    expect(fields.props('layout')).toBe('compact')
    expect(fields.props('showRemove')).toBe(true)
  })

  it('keeps parameter selection in the current preset rather than changing its application schema', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '参数选择')
    const addParameter = wrapper
      .findAllComponents({ name: 'AppSelect' })
      .find((select) => select.props('placeholder') === '+ 添加参数')!
    addParameter.vm.$emit('update:modelValue', '页码')
    await flushPromises()
    const fields = wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
    fields.vm.$emit('remove', '页码')
    await flushPromises()

    expect(fields.props('modelValue')).toEqual({})
    addParameter.vm.$emit('update:modelValue', '每页数量')
    await flushPromises()
    expect(fields.props('modelValue')).toEqual({ 每页数量: 20 })

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[0]![0].data.common_parameters).toEqual({
      每页数量: 20,
    })
    expect(mocks.save.mock.calls[0]![0].data.input_schema).toEqual(
      configuredSchema,
    )
  })

  it('keeps field edits local to the active preset and removes only deleted-field values', async () => {
    const wrapper = mountDialog({ schema: configuredSchema })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '配置 A')
    wrapper
      .findAllComponents({ name: 'AutomationParameterFields' })[0]!
      .vm.$emit('update:modelValue', { 页码: 2, 每页数量: 20 })
    ;(wrapper.vm as unknown as {
      applyInputSchema: (schema: AutomationInputSchemaDto) => void
    })
      .applyInputSchema({ fields: [configuredSchema.fields[0]] })
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()
    expect(mocks.save.mock.calls[0]![0].data).toMatchObject({
      input_schema: { fields: [configuredSchema.fields[0]] },
      common_parameters: { 页码: 2 },
    })
  })

  it('keeps A and B field selections isolated when the shared schema changes', async () => {
    const presetA = {
      preset_id: 'preset-a',
      app_id: application.app_id,
      name: '配置 A',
      input_schema: { fields: [configuredSchema.fields[0]] },
      common_parameters: { 页码: 2 },
      shop_overrides: { 'shop-a': { 页码: 3 } },
      version: 1,
    }
    const presetB = {
      preset_id: 'preset-b',
      app_id: application.app_id,
      name: '配置 B',
      input_schema: { fields: [configuredSchema.fields[1]] },
      common_parameters: { 每页数量: 20 },
      shop_overrides: {},
      version: 1,
    }
    mocks.presets = { data: ref([presetA, presetB]), isPending: ref(false) }
    const wrapper = mountDialog({
      initialPresetId: presetA.preset_id,
      schema: configuredSchema,
    })
    await flushPromises()

    const commonFields = () =>
      wrapper.findAllComponents({ name: 'AutomationParameterFields' })[0]!
    expect(commonFields().props('modelValue')).toEqual({ 页码: 2 })
    expect(commonFields().props('schema')).toEqual({
      fields: [configuredSchema.fields[0]],
    })

    // The mutable application template cannot reinterpret an already-saved
    // preset field contract. A remains exactly its persisted schema.
    await wrapper.setProps({ schema: expandedSchema })
    await flushPromises()
    expect(commonFields().props('modelValue')).toEqual({ 页码: 2 })
    expect(commonFields().props('schema')).toEqual({
      fields: [configuredSchema.fields[0]],
    })

    await wrapper.setProps({ initialPresetId: presetB.preset_id })
    await flushPromises()
    expect(commonFields().props('modelValue')).toEqual({ 每页数量: 20 })
    expect(commonFields().props('schema')).toEqual({
      fields: [configuredSchema.fields[1]],
    })
    expect(
      wrapper.findComponent({ name: 'AutomationParameterPresetShopOverrideDialog' }).props('schema'),
    ).toEqual({ fields: [configuredSchema.fields[1]] })
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
      .find((select) => select.props('placeholder') === '+ 添加参数')!
      .vm.$emit('update:modelValue', '页码')
    await flushPromises()
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
