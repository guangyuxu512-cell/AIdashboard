import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VNode } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type {
  CollectionTask,
  CollectionTaskPage,
  CollectionTaskService,
} from '../model/contracts'
import CollectionTasksPanel from './CollectionTasksPanel.vue'

const mocks = vi.hoisted(() => ({
  service: vi.fn(),
  message: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))
vi.mock('../api/collection-task-service', () => ({
  createCollectionTaskService: mocks.service,
  COLLECTION_TASKS_UNAVAILABLE: '尚未接入',
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async (original) => ({
  ...(await original<typeof import('naive-ui')>()),
  useMessage: () => mocks.message,
}))

function task(
  id = 'request-a',
  status: CollectionTask['status'] = 'failed',
): CollectionTask {
  return {
    id,
    status,
    platform: 'douyin',
    inputMode: 'product',
    inputValue: id,
    productId: '3832497447662387684',
    title: null,
    progress: 100,
    receiptId: id,
    ingestionState: 'failed',
    errorMessage: '安全失败原因',
    itemCount: 1,
    pendingCount: 0,
    runningCount: 0,
    succeededCount: 0,
    failedCount: 1,
    canceledCount: 0,
    items: [],
    createdAt: '2026-10-25T08:00:00+08:00',
    updatedAt: '2026-10-25T08:00:00+08:00',
  }
}
function page(item = task(), total = 1): CollectionTaskPage {
  return { items: [item], total, page: 1, pageSize: 20, counts: null }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((accept) => {
    resolve = accept
  })
  return { promise, resolve }
}
const passthrough = { template: '<div><slot /><slot name="actions" /></div>' }
const DetailStub = {
  name: 'CollectionTaskDetailDialog',
  props: ['show', 'task', 'busy'],
  emits: ['update:show', 'retry-item', 'recapture-item'],
  template: '<div v-if="show">{{ task?.id }}</div>',
}
function render(
  team: string | null = null,
  overrides: Partial<CollectionTaskService> = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.activeTeamId = team
  auth.teams = ['team-a', 'team-b'].map((teamId) => ({
    teamId,
    teamName: teamId,
    membershipId: null,
    roleCode: 'member',
    dataScope: 'team',
    teamEnabled: true,
    membershipEnabled: true,
  }))
  const service: CollectionTaskService = {
    available: true,
    mode: 'real',
    supportsListFilters: false,
    supportsShopCode: false,
    supportsAutomaticPdd: false,
    list: vi.fn().mockResolvedValue(page()),
    detail: vi.fn().mockResolvedValue(task()),
    create: vi.fn(),
    retry: vi.fn(),
    cancel: vi.fn(),
    retryItem: vi.fn().mockResolvedValue(task()),
    recaptureItem: vi.fn().mockResolvedValue(task()),
    ...overrides,
  }
  mocks.service.mockResolvedValue(service)
  const wrapper = mount(CollectionTasksPanel, {
    props: { contextKey: `actor:${team ?? 'none'}` },
    global: {
      plugins: [pinia],
      stubs: {
        CollectionTaskDetailDialog: DetailStub,
        PageSection: passthrough,
        ManagementListSection: passthrough,
        FilterBar: passthrough,
        FilterField: passthrough,
        DataTable: {
          name: 'DataTable',
          props: ['data', 'columns', 'checkedRowKeys', 'error', 'loading'],
          emits: ['update:checkedRowKeys'],
          template:
            '<div><span v-for="row in data" :key="row.id">{{ row.id }}</span></div>',
        },
        PaginationBar: {
          name: 'PaginationBar',
          props: ['itemCount'],
          template: '<div />',
        },
      },
    },
  })
  const table = () => wrapper.findComponent({ name: 'DataTable' })
  const detail = () => wrapper.findComponent(DetailStub)
  const actions = (row = task()): VNode[] =>
    table()
      .props('columns')
      .find((column: { key: string }) => column.key === 'actions')
      .render(row)
      .children.filter(Boolean)
  const open = () => actions()[0]!.props!.onClick()
  const button = (label: string) =>
    wrapper.findAll('button').find((node) => node.text() === label)!
  return { wrapper, service, auth, table, detail, open, actions, button }
}

describe('collection task read scope and context lifetime', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.useRealTimers())

  it('loads global list/count/detail while all mutations stay disabled', async () => {
    const view = render(null, {
      list: vi.fn().mockResolvedValue(page(task(), 2)),
    })
    await flushPromises()
    expect(view.service.list).toHaveBeenCalledOnce()
    expect(
      view.wrapper.findComponent({ name: 'PaginationBar' }).props('itemCount'),
    ).toBe(2)
    await view.open()
    await flushPromises()
    expect(view.detail().props('task').id).toBe('request-a')
    expect(view.detail().props('busy')).toBe(true)
    view.table().vm.$emit('update:checkedRowKeys', ['request-a'])
    await flushPromises()
    for (const label of ['创建采集任务', '批量重试', '取消选中任务'])
      expect(view.button(label).attributes('disabled')).toBeDefined()
    expect(view.actions()[1]!.props!.disabled).toBe(true)
    view.detail().vm.$emit('retry-item', 'item-a')
    view.detail().vm.$emit('recapture-item', 'item-a')
    view.actions()[1]!.props!.onClick()
    await flushPromises()
    expect(view.service.retry).not.toHaveBeenCalled()
    expect(view.service.retryItem).not.toHaveBeenCalled()
    expect(view.service.recaptureItem).not.toHaveBeenCalled()
    expect(view.service.cancel).not.toHaveBeenCalled()
    expect(view.service.create).not.toHaveBeenCalled()
    view.wrapper.unmount()
  })

  it('keeps the existing explicit-team actions available', async () => {
    const view = render('team-a')
    await flushPromises()
    expect(view.button('创建采集任务').attributes('disabled')).toBeUndefined()
    await view.open()
    expect(view.detail().props('busy')).toBe(false)
    view.detail().vm.$emit('retry-item', 'item-a')
    await flushPromises()
    expect(view.service.retryItem).toHaveBeenCalledWith('item-a')
    view.wrapper.unmount()
  })

  it('clears old details/selection immediately and refreshes on team switch', async () => {
    const view = render('team-a')
    await flushPromises()
    await view.open()
    view.table().vm.$emit('update:checkedRowKeys', ['request-a'])
    await flushPromises()
    vi.mocked(view.service.list).mockResolvedValueOnce(page(task('request-b')))
    view.auth.activeTeamId = 'team-b'
    await view.wrapper.setProps({ contextKey: 'actor:team-b' })
    expect(view.detail().props('task')).toBeNull()
    expect(view.detail().props('show')).toBe(false)
    await flushPromises()
    expect(view.table().props('data')[0].id).toBe('request-b')
    expect(view.table().props('checkedRowKeys')).toEqual([])
    expect(view.service.list).toHaveBeenCalledTimes(2)
    view.wrapper.unmount()
  })

  it('rejects a late list from the old scope', async () => {
    const old = deferred<CollectionTaskPage>()
    const view = render('team-a', {
      list: vi
        .fn()
        .mockReturnValueOnce(old.promise)
        .mockResolvedValue(page(task('request-b'))),
    })
    await flushPromises()
    await view.wrapper.setProps({ contextKey: 'actor:team-b' })
    await flushPromises()
    old.resolve(page(task('request-a'), 99))
    await flushPromises()
    expect(view.table().props('data')[0].id).toBe('request-b')
    expect(
      view.wrapper.findComponent({ name: 'PaginationBar' }).props('itemCount'),
    ).toBe(1)
    view.wrapper.unmount()
  })

  it('rejects a late detail from the old scope', async () => {
    const old = deferred<CollectionTask>()
    const view = render('team-a', {
      detail: vi.fn().mockReturnValue(old.promise),
    })
    await flushPromises()
    void view.open()
    await view.wrapper.setProps({ contextKey: 'actor:none' })
    await flushPromises()
    old.resolve(task())
    await flushPromises()
    expect(view.detail().props('task')).toBeNull()
    expect(view.detail().props('show')).toBe(false)
    view.wrapper.unmount()
  })

  it('does not let a background refresh cancel a newer detail selection', async () => {
    const next = deferred<CollectionTask>()
    const view = render('team-a', {
      detail: vi
        .fn()
        .mockResolvedValueOnce(task())
        .mockReturnValueOnce(next.promise)
        .mockResolvedValue(task()),
    })
    await flushPromises()
    await view.open()
    void view.actions(task('request-b'))[0]!.props!.onClick()
    await view.button('查询').trigger('click')
    await flushPromises()
    next.resolve(task('request-b'))
    await flushPromises()
    expect(view.detail().props('task').id).toBe('request-b')
    view.wrapper.unmount()
  })

  it('does not restart an old poll after the keyed panel is unmounted', async () => {
    vi.useFakeTimers()
    const old = deferred<CollectionTaskPage>()
    const view = render('team-a', {
      list: vi.fn().mockReturnValue(old.promise),
    })
    await flushPromises()
    view.wrapper.unmount()
    old.resolve(page(task('request-a', 'running')))
    await flushPromises()
    await vi.advanceTimersByTimeAsync(5000)
    expect(view.service.list).toHaveBeenCalledOnce()
  })
})
