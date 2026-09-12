import { flushPromises, shallowMount } from '@vue/test-utils'
import { NFormItem } from 'naive-ui'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'

import YingdaoApplicationConfigDialog from './YingdaoApplicationConfigDialog.vue'

const mocks = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  mutateAsync: vi.fn(),
  query: null as unknown,
}))

vi.mock('naive-ui', async (importOriginal) => ({
  ...(await importOriginal<typeof import('naive-ui')>()),
  useMessage: () => ({ error: mocks.error, success: mocks.success }),
}))

vi.mock('@/entities/automation-application', async (importOriginal) => ({
  ...(await importOriginal<
    typeof import('@/entities/automation-application')
  >()),
  useAutomationApplicationConfigQuery: () => mocks.query,
  useUpsertAutomationApplicationConfigMutation: () => ({
    isPending: ref(false),
    mutateAsync: mocks.mutateAsync,
  }),
}))

function configField(overrides: Record<string, unknown> = {}) {
  return {
    name: '商品列表',
    label: '',
    type: 'text' as const,
    required: true,
    default_value: '{"page":1}',
    options: [],
    ...overrides,
  }
}

function mountDialog(presetSchema?: { fields: ReturnType<typeof configField>[] }) {
  return shallowMount(YingdaoApplicationConfigDialog, {
    props: {
      show: true,
      application: {
        appId: 'yingdao-unicode-config',
        appName: '中文参数测试应用',
        versionId: '1',
      },
      ...(presetSchema ? { presetSchema } : {}),
    },
    global: { renderStubDefaultSlot: true },
  })
}

beforeEach(() => {
  mocks.error.mockReset()
  mocks.success.mockReset()
  mocks.mutateAsync.mockReset()
  mocks.mutateAsync.mockResolvedValue({})
  mocks.query = {
    data: ref({ input_schema: { fields: [configField()] } }),
    isPending: ref(false),
    error: ref(null),
  }
})

describe('YingdaoApplicationConfigDialog', () => {
  it('submits a Unicode name and JSON-looking text default without parsing it', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.findAllComponents(NFormItem)[1]!.props('label')).toBe(
      '显示名称（留空使用参数名）',
    )
    expect(mocks.mutateAsync).toHaveBeenCalledWith({
      appId: 'yingdao-unicode-config',
      data: {
        input_schema: {
          fields: [
            {
              name: '商品列表',
              label: '',
              type: 'text',
              required: true,
              default_value: '{"page":1}',
              options: [],
            },
          ],
        },
      },
    })
    const submitted =
      mocks.mutateAsync.mock.calls[0]![0].data.input_schema.fields[0]
        .default_value
    expect(typeof submitted).toBe('string')
  })

  it('returns a preset-local schema without mutating the application template', async () => {
    const schema = { fields: [configField()] }
    const wrapper = mountDialog(schema)
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.emitted('confirmPresetSchema')).toEqual([
      [
        {
          fields: [
            {
              name: '商品列表',
              label: '',
              type: 'text',
              required: true,
              default_value: '{"page":1}',
              options: [],
            },
          ],
        },
      ],
    ])
    expect(mocks.mutateAsync).not.toHaveBeenCalled()
  })

  it('shows a client name error and keeps the draft without sending a request', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.findAllComponents(AppInput)[0]!.vm.$emit('update:modelValue', '')
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(mocks.mutateAsync).not.toHaveBeenCalled()
    expect(wrapper.findAllComponents(NFormItem)[0]!.props('feedback')).toBe(
      '请输入参数名',
    )
    expect(wrapper.emitted('update:show')).toBeUndefined()
  })

  it('blocks duplicate names and invalid select options/defaults at their rows', async () => {
    mocks.query = {
      data: ref({
        input_schema: {
          fields: [
            configField(),
            configField({
              name: '商品列表',
              label: '状态',
              type: 'select',
              default_value: 'unknown',
              options: [],
            }),
          ],
        },
      }),
      isPending: ref(false),
      error: ref(null),
    }
    const wrapper = mountDialog()
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    const feedback = wrapper
      .findAllComponents(NFormItem)
      .map((item) => item.props('feedback'))
    expect(mocks.mutateAsync).not.toHaveBeenCalled()
    expect(feedback).toContain('参数名不能重复')
    expect(feedback).toContain('状态必须提供不重复的选项')
    expect(feedback).toContain('状态的默认值不符合select类型')
  })

  it('maps the duplicate-name details emitted by the API to both affected rows', async () => {
    mocks.query = {
      data: ref({
        input_schema: {
          fields: [configField(), configField({ name: '商品编号' })],
        },
      }),
      isPending: ref(false),
      error: ref(null),
    }
    mocks.mutateAsync.mockRejectedValue(
      new ApiError({
        code: 'VALIDATION_ERROR',
        message: '请求参数校验失败',
        details: [
          {
            loc: ['body', 'input_schema', 'fields', 0, 'name'],
            msg: '参数名不能重复',
          },
          {
            loc: ['body', 'input_schema', 'fields', 1, 'name'],
            msg: '参数名不能重复',
          },
        ],
      }),
    )
    const wrapper = mountDialog()
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(
      wrapper
        .findAllComponents(NFormItem)
        .map((item) => item.props('feedback'))
        .filter((feedback) => feedback === '参数名不能重复'),
    ).toHaveLength(2)
    expect(wrapper.findAllComponents(AppInput)[0]!.props('modelValue')).toBe(
      '商品列表',
    )
    expect(wrapper.emitted('update:show')).toBeUndefined()
    expect(mocks.error).not.toHaveBeenCalled()
  })
})
