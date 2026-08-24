import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BusinessSkillCatalogItemViewModel } from '@/entities/business-skill'
import FormDialog from '@/shared/components/FormDialog.vue'
import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

import ScheduleFormDialog from './ScheduleFormDialog.vue'

const queryMocks = vi.hoisted(() => ({
  business: null as unknown,
  inventory: null as unknown,
  config: null as unknown,
}))

vi.mock('@/entities/business-skill', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/business-skill')>()),
  useBusinessSkillCatalogQuery: () => queryMocks.business,
}))

vi.mock('@/entities/device', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/device')>()),
  useDeviceProviderInventoriesQuery: () => queryMocks.inventory,
}))

vi.mock('@/entities/automation-application', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/automation-application')>()),
  useAutomationApplicationConfigQuery: () => queryMocks.config,
}))

const skill: BusinessSkillCatalogItemViewModel = {
  deviceId: 'device-1',
  skillId: 'catalog.fixture.run',
  displayName: '目录测试能力',
  version: '1.0.0',
  availability: 'available',
  unavailableReason: null,
  inputSchema: {
    type: 'object',
    properties: { keyword: { type: 'string' } },
    required: ['keyword'],
    additionalProperties: false,
  },
  parameterFields: [
    {
      name: 'keyword',
      label: '关键词',
      control: 'string',
      valueType: 'string',
      required: true,
      hasDefault: false,
    },
  ],
  configurable: true,
}

beforeEach(() => {
  queryMocks.business = {
    data: ref([skill]),
    isPending: ref(false),
    error: ref(null),
  }
  queryMocks.inventory = {
    data: ref({ applications: [] }),
    isPending: ref(false),
    error: ref(null),
  }
  queryMocks.config = {
    data: ref({ input_schema: { fields: [] } }),
    isPending: ref(false),
    error: ref(null),
  }
})

function mountDialog() {
  return shallowMount(ScheduleFormDialog, {
    props: {
      show: true,
      mode: 'create',
      schedule: null,
      deviceOptions: [{ label: '设备一', value: 'device-1' }],
    },
    global: { renderStubDefaultSlot: true },
  })
}

async function chooseBusinessSkill(
  wrapper: ReturnType<typeof mountDialog>,
): Promise<void> {
  const selects = wrapper.findAllComponents(AppSelect)
  selects[0]!.vm.$emit('update:modelValue', 'device-1')
  selects[1]!.vm.$emit('update:modelValue', 'business_skill')
  await flushPromises()
  const businessSelect = wrapper
    .findAllComponents(AppSelect)
    .find((select) => select.props('placeholder')?.includes('业务 Skill'))
  expect(businessSelect).toBeDefined()
  businessSelect!.vm.$emit('update:modelValue', 'catalog.fixture.run')
  await flushPromises()
}

describe('ScheduleFormDialog Business Skill target', () => {
  it('uses the device-scoped catalog schema and emits ordinary Task input', async () => {
    const wrapper = mountDialog()
    await chooseBusinessSkill(wrapper)

    const parameterFields = wrapper.findComponent(SchemaParameterFields)
    expect(parameterFields.props('fields')).toEqual(skill.parameterFields)
    parameterFields.vm.$emit('update:modelValue', { keyword: 'safe' })
    wrapper
      .findComponent(AppInput)
      .vm.$emit('update:modelValue', '每日目录测试')
    await flushPromises()
    expect(wrapper.findComponent(FormDialog).props('submitDisabled')).toBe(false)
    wrapper.findComponent(FormDialog).vm.$emit('submit')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      name: '每日目录测试',
      deviceId: 'device-1',
      executionType: 'business_skill',
      applicationId: null,
      skillId: 'catalog.fixture.run',
      parameters: { keyword: 'safe' },
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
  })

  it('shows a normal empty state instead of Internal Skills or an error', async () => {
    ;(
      queryMocks.business as {
        data: { value: BusinessSkillCatalogItemViewModel[] }
      }
    ).data.value = []
    const wrapper = mountDialog()
    await chooseBusinessSkill(wrapper)

    expect(wrapper.text()).toContain('当前 Worker 尚未安装业务 Skill')
    expect(wrapper.text()).not.toContain('加载失败')
    expect(wrapper.text()).not.toContain('system.echo')
  })
})
