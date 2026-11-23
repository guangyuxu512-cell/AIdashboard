import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DataTable from '@/shared/components/DataTable.vue'
import WorkerShopsPage from './WorkerShopsPage.vue'

const mocks = vi.hoisted(() => ({
  auth: null as unknown as { currentUser: { userId: string }; activeTeamId: string | null },
  query: null as unknown,
  options: null as unknown as { queryKey: { value: unknown } },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@tanstack/vue-query', () => ({
  useQuery: (options: unknown) => { mocks.options = options as typeof mocks.options; return mocks.query },
}))

beforeEach(() => {
  mocks.auth = reactive({ currentUser: { userId: 'user-1' }, activeTeamId: null })
  const shop = { local_shop_id: 'local-1', platform_shop_id: '123', shop_name: '同一家店',
    platform: 'douyin', session_status: 'valid', status_observed_at: '2026-11-23T05:00:00Z',
    compass_session_status: 'unknown', compass_status_observed_at: null }
  mocks.query = { data: ref([
    { device_id: 'device-1', device_name: '设备一', device_enabled: true, available: true,
      worker_runtime: { connection_status: 'online' }, shops: [shop] },
    { device_id: 'device-2', device_name: '设备二', device_enabled: true, available: false,
      worker_runtime: { connection_status: 'offline' }, shops: [{ ...shop, compass_session_status: 'invalid' }] },
  ]), isFetching: ref(false), isLoading: ref(false), error: ref(null), refetch: vi.fn() }
})

describe('Worker shop overview', () => {
  it('keeps the same shop separate per device and displays distinct service statuses', () => {
    const wrapper = shallowMount(WorkerShopsPage, { global: { renderStubDefaultSlot: true } })
    const table = wrapper.findComponent(DataTable)
    const rows = table.props('data') as Array<{ rowKey: string }>
    expect(rows.map((row) => row.rowKey)).toEqual(['device-1:local-1', 'device-2:local-1'])
    const columns = table.props('columns') as unknown as Array<{
      key: string; render: (row: { rowKey: string }) => { props: { label: string } }
    }>
    expect(columns.find((col) => col.key === 'session_status')!.render(rows[0]).props.label).toBe('有效')
    expect(columns.find((col) => col.key === 'compass_session_status')!.render(rows[0]).props.label).toBe('未确认')
    expect(columns.find((col) => col.key === 'compass_session_status')!.render(rows[1]).props.label).toBe('失效')
    expect(columns.find((col) => col.key === 'online')!.render(rows[1]).props.label).toBe('不可用')
    const nonDouyin = { ...rows[0], platform: 'pdd' }
    expect(columns.find((col) => col.key === 'session_status')!.render(nonDouyin)).toBe('—')
    expect(columns.find((col) => col.key === 'compass_session_status')!.render(nonDouyin)).toBe('—')
  })

  it('keys the overview by user and team to prevent stale cross-team results', () => {
    shallowMount(WorkerShopsPage, { global: { renderStubDefaultSlot: true } })
    expect(mocks.options.queryKey.value).toEqual(['devices', 'shop-overview', 'user-1', null])
    mocks.auth.activeTeamId = 'team-2'
    expect(mocks.options.queryKey.value).toEqual(['devices', 'shop-overview', 'user-1', 'team-2'])
  })
})
