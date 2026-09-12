import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ShopMultiSelector } from '@/entities/shop'
import { AssetMultiSelector } from '@/entities/asset'
import {
  AutomationParameterFields,
  AutomationParameterPresetSelector,
} from '@/entities/automation-application'
import AppDialog from '@/shared/ui/AppDialog.vue'

import YingdaoApplicationRunDialog from './YingdaoApplicationRunDialog.vue'

const mocks = vi.hoisted(() => ({
  createTask: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  shops: null as unknown,
  config: null as unknown,
}))

vi.mock('naive-ui', async (importOriginal) => ({
  ...(await importOriginal<typeof import('naive-ui')>()),
  useMessage: () => ({ error: mocks.error, success: mocks.success }),
}))

vi.mock('@/entities/task', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/task')>()),
  useCreateTaskMutation: () => ({
    isPending: ref(false),
    mutateAsync: mocks.createTask,
  }),
}))

vi.mock('@/entities/shop', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/shop')>()),
  useDeviceShopSelectionOptionsQuery: () => mocks.shops,
}))

vi.mock('@/entities/automation-application', async (importOriginal) => ({
  ...(await importOriginal<
    typeof import('@/entities/automation-application')
  >()),
  useAutomationApplicationConfigQuery: () => mocks.config,
}))

beforeEach(() => {
  mocks.createTask.mockReset()
  mocks.createTask.mockResolvedValue({ task_id: 'task-1' })
  mocks.error.mockReset()
  mocks.success.mockReset()
  mocks.shops = {
    data: ref(
      Array.from({ length: 5 }, (_, index) => ({
        label: `店铺${index + 1}`,
        value: `shop-${index + 1}`,
      })),
    ),
    isPending: ref(false),
    error: ref(null),
  }
  mocks.config = {
    data: ref({ input_schema: { fields: [] } }),
    isPending: ref(false),
    error: ref(null),
  }
})

describe('YingdaoApplicationRunDialog', () => {
  it('defaults all bound shops and creates only one multi-shop Task', async () => {
    const wrapper = shallowMount(YingdaoApplicationRunDialog, {
      props: {
        show: true,
        application: {
          appId: 'safe-app',
          appName: '安全测试应用',
          versionId: '1',
        },
        deviceId: 'device-1',
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()
    const dialog = wrapper.findComponent(AppDialog)
    const selector = wrapper.findComponent(ShopMultiSelector)
    expect(selector.props('modelValue')).toEqual([
      'shop-1',
      'shop-2',
      'shop-3',
      'shop-4',
      'shop-5',
    ])
    expect(dialog.props('positiveDisabled')).toBe(false)

    selector.vm.$emit('update:modelValue', ['shop-1', 'shop-3', 'shop-5'])
    wrapper
      .findComponent(AssetMultiSelector)
      .vm.$emit('update:modelValue', ['asset-2', 'asset-1'])
    await flushPromises()
    expect(dialog.props('positiveDisabled')).toBe(false)

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledWith({
      target_device_id: 'device-1',
      shop_ids: ['shop-1', 'shop-3', 'shop-5'],
      asset_ids: ['asset-2', 'asset-1'],
      skill_id: 'yingdao.app.run',
      input: { app_id: 'safe-app', params: {} },
    })
    expect(wrapper.emitted('started')).toEqual([['task-1']])
    expect(mocks.createTask).toHaveBeenCalledTimes(1)
  })

  it('creates a no-shop Task after all bound shops are explicitly deselected', async () => {
    const wrapper = shallowMount(YingdaoApplicationRunDialog, {
      props: {
        show: true,
        application: {
          appId: 'safe-app',
          appName: '安全测试应用',
          versionId: '1',
        },
        deviceId: 'device-1',
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()
    wrapper.findComponent(ShopMultiSelector).vm.$emit('update:modelValue', [])
    ;(
      mocks.shops as {
        data: { value: Array<{ label: string; value: string }> }
      }
    ).data.value = [{ label: '刷新后的店铺', value: 'shop-refreshed' }]
    await flushPromises()

    const dialog = wrapper.findComponent(AppDialog)
    expect(
      wrapper.findComponent(ShopMultiSelector).props('modelValue'),
    ).toEqual([])
    expect(dialog.props('positiveDisabled')).toBe(false)
    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledWith({
      target_device_id: 'device-1',
      shop_ids: [],
      asset_ids: [],
      skill_id: 'yingdao.app.run',
      input: { app_id: 'safe-app', params: {} },
    })
  })

  it('clears a selected preset when the execution device changes', async () => {
    const wrapper = shallowMount(YingdaoApplicationRunDialog, {
      props: {
        show: true,
        application: {
          appId: 'safe-app',
          appName: '安全测试应用',
          versionId: '1',
        },
        deviceId: 'device-1',
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()
    wrapper
      .findComponent(AutomationParameterPresetSelector)
      .vm.$emit('update:modelValue', 'preset-for-device-1')
    await flushPromises()

    await wrapper.setProps({ deviceId: 'device-2' })
    await flushPromises()
    wrapper.findComponent(AppDialog).vm.$emit('confirm')
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledWith({
      target_device_id: 'device-2',
      shop_ids: ['shop-1', 'shop-2', 'shop-3', 'shop-4', 'shop-5'],
      asset_ids: [],
      skill_id: 'yingdao.app.run',
      input: { app_id: 'safe-app', params: {} },
    })
  })

  it('does not expose or submit a legacy template until manual mode is explicit', async () => {
    mocks.config = {
      data: ref({
        input_schema: {
          fields: [
            {
              name: '页码',
              label: '页码',
              type: 'number',
              required: false,
              default_value: 1,
              options: [],
            },
          ],
        },
      }),
      isPending: ref(false),
      error: ref(null),
    }
    const wrapper = shallowMount(YingdaoApplicationRunDialog, {
      props: {
        show: true,
        application: {
          appId: 'legacy-template-app',
          appName: '旧模板应用',
          versionId: '1',
        },
        deviceId: 'device-1',
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    const dialog = wrapper.findComponent(AppDialog)
    expect(dialog.props('positiveDisabled')).toBe(true)
    expect(wrapper.findComponent(AutomationParameterFields).exists()).toBe(false)

    wrapper
      .findComponent(AutomationParameterPresetSelector)
      .vm.$emit('update:manualMode', true)
    await flushPromises()

    expect(dialog.props('positiveDisabled')).toBe(false)
    expect(wrapper.findComponent(AutomationParameterFields).exists()).toBe(true)
    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({
        input: { app_id: 'legacy-template-app', params: { 页码: 1 } },
      }),
    )
  })
})
