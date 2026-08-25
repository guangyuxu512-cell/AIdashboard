import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ShopSelector } from '@/entities/shop'
import AppDialog from '@/shared/ui/AppDialog.vue'

import YingdaoApplicationRunDialog from './YingdaoApplicationRunDialog.vue'

const mocks = vi.hoisted(() => ({
  createTask: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
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

vi.mock('@/entities/automation-application', async (importOriginal) => ({
  ...(await importOriginal<
    typeof import('@/entities/automation-application')
  >()),
  useAutomationApplicationConfigQuery: () => ({
    data: ref({ input_schema: { fields: [] } }),
    isPending: ref(false),
    error: ref(null),
  }),
}))

beforeEach(() => {
  mocks.createTask.mockReset()
  mocks.createTask.mockResolvedValue({ task_id: 'task-1' })
  mocks.error.mockReset()
  mocks.success.mockReset()
})

describe('YingdaoApplicationRunDialog', () => {
  it('requires a shop and sends shop_id outside the Task input payload', async () => {
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
    const dialog = wrapper.findComponent(AppDialog)
    expect(dialog.props('positiveDisabledReason')).toBe(
      '请选择本次任务使用的店铺账号',
    )

    wrapper
      .findComponent(ShopSelector)
      .vm.$emit('update:modelValue', 'shop-1')
    await flushPromises()
    expect(dialog.props('positiveDisabled')).toBe(false)

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledWith({
      target_device_id: 'device-1',
      shop_id: 'shop-1',
      skill_id: 'yingdao.app.run',
      input: { app_id: 'safe-app', params: {} },
    })
    expect(wrapper.emitted('started')).toEqual([['task-1']])
  })
})
