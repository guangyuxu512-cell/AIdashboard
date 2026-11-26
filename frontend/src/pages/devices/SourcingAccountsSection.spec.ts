import { shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import DataTable from '@/shared/components/DataTable.vue'
import SourcingAccountsSection from './SourcingAccountsSection.vue'

const { now } = vi.hoisted(() => ({ now:Math.floor(Date.now() / 1000) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ currentUser:{ userId:'admin' } }) }))
vi.mock('@tanstack/vue-query', () => ({ useQuery: () => ({ data:ref([
  { reporterId:'one', deviceName:'设备一', online:true, appVersion:'0.1.5', lastSeenAt:now,
    accounts:[{ accountId:'a', name:'账号 A', sessionStatus:'valid', sessionCheckedAt:now, workStatus:'working' }] },
  { reporterId:'two', deviceName:'设备二', online:false, appVersion:'0.1.5', lastSeenAt:now - 120,
    accounts:[{ accountId:'a', name:'账号 A', sessionStatus:'expired', sessionCheckedAt:now, workStatus:'working' }] },
  { reporterId:'three', deviceName:'设备三', online:true, appVersion:'0.1.5', lastSeenAt:now, accounts:[] },
]), isFetching:ref(false), isLoading:ref(false), error:ref(null), refetch:vi.fn() }) }))

describe('1688 account overview', () => {
  it('keeps installations separate and never describes an offline worker as working', () => {
    const wrapper = shallowMount(SourcingAccountsSection, { global:{ renderStubDefaultSlot:true } })
    const table = wrapper.findComponent(DataTable)
    const rows = table.props('data') as Array<{ key:string }>
    expect(rows.map((row) => row.key)).toEqual(['one:a', 'two:a', 'three:empty'])
    const columns = table.props('columns') as unknown as Array<{ key:string; render:(row:unknown) => { props:{ label:string } } | string }>
    expect((columns.find((col) => col.key === 'session')!.render(rows[0]) as { props:{ label:string } }).props.label).toBe('有效')
    expect((columns.find((col) => col.key === 'session')!.render(rows[1]) as { props:{ label:string } }).props.label).toBe('已失效')
    expect(columns.find((col) => col.key === 'work')!.render(rows[0])).toBe('工作中')
    expect(columns.find((col) => col.key === 'work')!.render(rows[1])).toBe('—')
  })
})
