import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref, type Ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AutomationParameterPresetDto } from '@/entities/automation-application'

import { useParameterPresetManagement } from './useParameterPresetManagement'

const preset: AutomationParameterPresetDto = {
  preset_id: 'preset-last-page',
  team_id: 'team-1',
  created_by_user_id: 'user-1',
  app_id: 'app-1',
  name: '最后一页配置',
  input_schema: { fields: [] },
  common_parameters: {},
  shop_overrides: {},
  invalid_parameter_names: [],
  version: 1,
  created_at: '2026-09-13T00:00:00Z',
  updated_at: '2026-09-13T00:00:00Z',
}

interface ManagementListParams {
  deviceId: string | null
  appId: string | null
  query: string | null
  page: number
  pageSize: number
}

const mocks = vi.hoisted(() => ({
  applications: null as unknown,
  list: null as unknown,
  listParams: null as unknown,
  copy: null as unknown,
  remove: null as unknown,
}))

vi.mock('@/entities/automation-application', () => ({
  useYingdaoApplicationOptionsQuery: () => mocks.applications,
  useAutomationParameterPresetManagementQuery: (params: unknown) => {
    mocks.listParams = params
    return mocks.list
  },
  useCopyAutomationParameterPresetMutation: () => mocks.copy,
  useRemoveAutomationParameterPresetMutation: () => mocks.remove,
}))

vi.mock('@/entities/device', () => ({
  useDeviceListQuery: () => ({
    data: ref({ items: [], total: 0, page: 1, pageSize: 100 }),
    isPending: ref(false),
    error: ref(null),
  }),
  useDeviceProviderInventoriesQuery: () => ({
    data: ref(null),
    isPending: ref(false),
    error: ref(null),
  }),
}))

function listParams(): ManagementListParams {
  return (mocks.listParams as Ref<ManagementListParams>).value
}

function mountManagement() {
  let management: ReturnType<typeof useParameterPresetManagement> | null = null
  const Harness = defineComponent({
    setup() {
      management = useParameterPresetManagement()
      return () => h('div')
    },
  })
  mount(Harness)
  return management as unknown as ReturnType<typeof useParameterPresetManagement>
}

beforeEach(() => {
  mocks.applications = {
    data: ref([{ app_id: 'app-1', app_name: '采集应用' }]),
    isPending: ref(false),
    error: ref(null),
    isSuccess: ref(true),
    refetch: vi.fn(),
  }
  mocks.list = {
    data: ref({ items: [preset], total: 21, page: 1, page_size: 20 }),
    isPending: ref(false),
    error: ref(null),
    refetch: vi.fn().mockResolvedValue(undefined),
  }
  mocks.copy = { mutateAsync: vi.fn(), isPending: ref(false) }
  mocks.remove = { mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: ref(false) }
  mocks.listParams = null
})

describe('useParameterPresetManagement', () => {
  it('resets filters to the first page and changes page size through the shared Page contract', async () => {
    const management = mountManagement()

    management.setPage(2)
    management.setPageSize(50)
    expect(listParams()).toEqual({ deviceId: null, appId: null, query: null, page: 1, pageSize: 50 })

    management.searchDraft.value = ' 日常 '
    management.selectedAppIdDraft.value = 'app-1'
    management.query()
    expect(listParams()).toEqual({
      appId: 'app-1',
      deviceId: null,
      query: '日常',
      page: 1,
      pageSize: 50,
    })

    management.reset()
    await flushPromises()
    expect(listParams()).toEqual({ deviceId: null, appId: null, query: null, page: 1, pageSize: 50 })
  })

  it('returns to a valid page after deleting the final row of a later page', async () => {
    const management = mountManagement()
    management.setPage(2)
    ;(
      mocks.list as {
        data: Ref<{ items: AutomationParameterPresetDto[]; total: number; page: number; page_size: number }>
      }
    ).data.value = { items: [preset], total: 21, page: 2, page_size: 20 }
    management.requestRemove(preset)

    await management.confirmRemove()

    expect(
      (mocks.remove as { mutateAsync: unknown }).mutateAsync,
    ).toHaveBeenCalledWith({ appId: 'app-1', presetId: 'preset-last-page' })
    expect(listParams()).toEqual({ deviceId: null, appId: null, query: null, page: 1, pageSize: 20 })
  })

  it('does not reinterpret an unknown application display name as an app id', () => {
    const management = mountManagement()
    management.selectedAppIdDraft.value = '111'

    expect(management.invalidSelectedApp.value).toBe(true)
    management.openCreate()
    expect(management.editorAppId.value).toBeNull()
  })
})
