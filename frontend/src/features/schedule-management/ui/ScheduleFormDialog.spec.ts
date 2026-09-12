import { flushPromises, shallowMount } from '@vue/test-utils'
import { NCheckboxGroup } from 'naive-ui'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BusinessSkillCatalogItemViewModel } from '@/entities/business-skill'
import { AutomationParameterPresetSelector } from '@/entities/automation-application'
import type { ScheduleDetailViewModel } from '@/entities/schedule'
import { ShopMultiSelector } from '@/entities/shop'
import FormDialog from '@/shared/components/FormDialog.vue'
import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

import ScheduleFormDialog from './ScheduleFormDialog.vue'

const queryMocks = vi.hoisted(() => ({
  business: null as unknown,
  inventory: null as unknown,
  config: null as unknown,
  shops: null as unknown,
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

vi.mock('@/entities/shop', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/shop')>()),
  useDeviceShopSelectionOptionsQuery: () => queryMocks.shops,
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
  queryMocks.shops = {
    data: ref([
      { label: '店铺一', value: 'shop-fixture-001' },
      { label: '店铺二', value: 'shop-fixture-002' },
      { label: '店铺三', value: 'shop-fixture-003' },
    ]),
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

const savedSchedule: ScheduleDetailViewModel = {
  scheduleId: 'schedule-1',
  name: '已保存计划',
  enabled: true,
  deviceId: 'device-1',
  shopIds: ['shop-fixture-001', 'shop-fixture-003'],
  deviceName: '设备一',
  executionType: 'business_skill',
  executionTypeDisplay: '业务 Skill',
  skillId: 'catalog.fixture.run',
  executionName: '目录测试能力',
  scheduleType: 'daily',
  localTime: '09:00',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  localDate: null,
  weekdays: [],
  triggerRuleDisplay: '每日 09:00',
  nextRunAt: null,
  nextRunAtDisplay: '—',
  latestRun: null,
  createdAt: '2026-08-26T00:00:00Z',
  createdAtDisplay: '2026-08-26 08:00',
  updatedAt: '2026-08-26T00:00:00Z',
  updatedAtDisplay: '2026-08-26 08:00',
  applicationId: null,
  parameterPresetId: null,
  parameters: { keyword: 'saved' },
}

async function chooseBusinessSkill(
  wrapper: ReturnType<typeof mountDialog>,
): Promise<void> {
  const selects = wrapper.findAllComponents(AppSelect)
  selects[0]!.vm.$emit('update:modelValue', 'device-1')
  await flushPromises()
  selects[1]!.vm.$emit('update:modelValue', 'business_skill')
  wrapper
    .findComponent(ShopMultiSelector)
    .vm.$emit('update:modelValue', [
      'shop-fixture-001',
      'shop-fixture-003',
    ])
  await flushPromises()
  const businessSelect = wrapper
    .findAllComponents(AppSelect)
    .find((select) => select.props('placeholder')?.includes('业务 Skill'))
  expect(businessSelect).toBeDefined()
  businessSelect!.vm.$emit('update:modelValue', 'catalog.fixture.run')
  await flushPromises()
}

describe('ScheduleFormDialog Business Skill target', () => {
  it('uses the shared parameter preset selector for a Yingdao schedule', () => {
    const wrapper = mountDialog()

    expect(wrapper.findComponent(AutomationParameterPresetSelector).exists()).toBe(
      true,
    )
  })

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
      shopIds: ['shop-fixture-001', 'shop-fixture-003'],
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

  it('keeps the saved shop set when a newly bound shop appears during edit', async () => {
    ;(
      queryMocks.shops as {
        data: { value: Array<{ label: string; value: string }> }
      }
    ).data.value.push({ label: '后来绑定店铺', value: 'shop-fixture-004' })
    const wrapper = shallowMount(ScheduleFormDialog, {
      props: {
        show: true,
        mode: 'edit',
        schedule: savedSchedule,
        deviceOptions: [{ label: '设备一', value: 'device-1' }],
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    expect(wrapper.findComponent(ShopMultiSelector).props('modelValue')).toEqual([
      'shop-fixture-001',
      'shop-fixture-003',
    ])
  })

  it('keeps an explicit empty selection when the bound shop list refreshes', async () => {
    const wrapper = mountDialog()
    await chooseBusinessSkill(wrapper)
    wrapper
      .findComponent(AppInput)
      .vm.$emit('update:modelValue', '无店铺计划')
    wrapper
      .findComponent(SchemaParameterFields)
      .vm.$emit('update:modelValue', { keyword: 'safe' })

    const shopSelector = wrapper.findComponent(ShopMultiSelector)
    shopSelector.vm.$emit('update:modelValue', [])
    ;(
      queryMocks.shops as {
        data: { value: Array<{ label: string; value: string }> }
      }
    ).data.value = [
      { label: '店铺一', value: 'shop-fixture-001' },
      { label: '店铺二', value: 'shop-fixture-002' },
      { label: '新增绑定店铺', value: 'shop-fixture-004' },
    ]
    await flushPromises()

    expect(shopSelector.props('modelValue')).toEqual([])
    const dialog = wrapper.findComponent(FormDialog)
    expect(dialog.props('submitDisabled')).toBe(false)
    dialog.vm.$emit('submit')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      shopIds: [],
      executionType: 'business_skill',
      skillId: 'catalog.fixture.run',
    })
  })

  it('requires and emits the selected ISO weekdays for a weekly plan', async () => {
    const wrapper = mountDialog()
    await chooseBusinessSkill(wrapper)
    wrapper
      .findComponent(AppInput)
      .vm.$emit('update:modelValue', '每周目录测试')
    wrapper
      .findComponent(SchemaParameterFields)
      .vm.$emit('update:modelValue', { keyword: 'safe' })
    wrapper.findComponent(AppRadio).vm.$emit('update:modelValue', 'weekly')
    await flushPromises()

    const weekdays = wrapper.findComponent(NCheckboxGroup)
    expect(weekdays.exists()).toBe(true)
    expect(wrapper.findComponent(FormDialog).props('submitDisabled')).toBe(true)
    weekdays.vm.$emit('update:value', [1, 3, 5])
    await flushPromises()
    expect(wrapper.findComponent(FormDialog).props('submitDisabled')).toBe(false)
    wrapper.findComponent(FormDialog).vm.$emit('submit')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      scheduleType: 'weekly',
      localDate: null,
      weekdays: [1, 3, 5],
    })
  })
})
