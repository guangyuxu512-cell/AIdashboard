import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, type VNode } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type {
  LibraryProduct,
  ProductLibraryPage,
  ProductLibraryService,
} from '../model/contracts'
import ProductLibraryWorkspace from './ProductLibraryWorkspace.vue'

const mocks = vi.hoisted(() => ({
  service: vi.fn(),
  route: { query: {} as Record<string, string> },
  router: { replace: vi.fn() },
  message: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('../api/product-library-service', () => ({
  createProductLibraryService: mocks.service,
  PRODUCT_LIBRARY_UNAVAILABLE: '尚未接入',
}))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}))
vi.mock('naive-ui', async (original) => ({
  ...(await original<typeof import('naive-ui')>()),
  useMessage: () => mocks.message,
}))

function product(id: string, groupId: string | null): LibraryProduct {
  return {
    id,
    productId: `source-${id}`,
    platform: 'douyin',
    title: id,
    groupId,
    groupName: groupId,
    category: null,
    currentPrice: null,
    currency: null,
    collectedAt: '2026-10-26T08:00:00+08:00',
    sourceUrl: null,
    mainImageUrl: null,
    detailImageUrls: [],
    specDimensions: [],
    skus: [],
    attributes: [],
    mockEditedAt: null,
    packageFiles: [],
    history: [],
  }
}

function page(item: LibraryProduct): ProductLibraryPage {
  return { items: [item], total: 1, page: 1, pageSize: 20, categories: [] }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((accept) => {
    resolve = accept
  })
  return { promise, resolve }
}

function service(
  scope: string,
  overrides: Partial<ProductLibraryService> = {},
): ProductLibraryService {
  const item = product(`product-${scope}`, `group-${scope}`)
  const unavailable = vi.fn().mockRejectedValue(new Error('不可用'))
  return {
    available: true,
    mode: 'real',
    capabilities: {
      platformFilter: false,
      categoryFilter: false,
      edit: false,
      createGroup: false,
      moveGroup: false,
      remove: false,
      recollect: false,
      import: false,
      export: true,
      batchExport: false,
    },
    groups: vi
      .fn()
      .mockResolvedValue([
        { id: `group-${scope}`, name: `分组 ${scope}`, count: null },
      ]),
    list: vi.fn().mockResolvedValue(page(item)),
    detail: vi.fn().mockResolvedValue(item),
    saveEdit: unavailable,
    createGroup: unavailable,
    moveToGroup: unavailable,
    remove: unavailable,
    recollect: unavailable,
    exportSingle: vi.fn(),
    ...overrides,
  }
}

const passthrough = {
  template:
    '<div><slot /><slot name="actions" /><slot name="primary-action" /></div>',
}
const PreviewStub = {
  name: 'ProductPreviewDialog',
  props: ['show', 'product'],
  emits: ['update:show'],
  template: '<div v-if="show">{{ product?.id }}</div>',
}

function render(
  services: ProductLibraryService[],
  view: 'all' | 'grouped' = 'all',
  initialTeam: string | null = 'team-a',
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.currentUser = { userId: 'actor', displayName: '管理员' }
  auth.activeTeamId = initialTeam
  mocks.route.query = view === 'grouped' ? { view: 'grouped' } : {}
  for (const source of services) mocks.service.mockResolvedValueOnce(source)
  const wrapper = mount(ProductLibraryWorkspace, {
    global: {
      plugins: [pinia],
      stubs: {
        ProductPreviewDialog: PreviewStub,
        ProductExportDialog: true,
        ProductImportDialog: true,
        ProductGroupDialog: true,
        ContextSwitchBar: passthrough,
        FilterBar: passthrough,
        FilterField: passthrough,
        ManagementListSection: passthrough,
        TableToolbar: passthrough,
        ErrorState: true,
        EmptyState: true,
        LoadingState: true,
        AppInput: true,
        AppSelect: true,
        AppButton: { template: '<button><slot /></button>' },
        DataTable: {
          name: 'DataTable',
          props: ['data', 'columns', 'checkedRowKeys'],
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
  const preview = () => wrapper.findComponent(PreviewStub)
  const actions = (row: LibraryProduct): VNode[] =>
    table()
      .props('columns')
      .find((column: { key: string }) => column.key === 'actions')
      .render(row)
      .children.filter(Boolean)
  const open = (row: LibraryProduct): Promise<void> =>
    actions(row)[0]!.props!.onClick()
  const exportProduct = (row: LibraryProduct): Promise<void> =>
    actions(row)[1]!.props!.onClick()
  return { wrapper, auth, table, preview, actions, open, exportProduct }
}

describe('product library scope lifetime', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
  })

  it('loads the all-team read scope without requiring a selected team', async () => {
    const source = service('all')
    const view = render([source], 'all', null)
    await flushPromises()
    expect(source.groups).toHaveBeenCalled()
    expect(source.list).toHaveBeenCalled()
    expect(view.table().props('data')[0].id).toBe('product-all')
    view.wrapper.unmount()
  })

  it('clears detail, selection and the old group before loading a new team', async () => {
    const first = service('a')
    const second = service('b')
    const view = render([first, second], 'grouped')
    await flushPromises()
    await view.open(product('product-a', 'group-a'))
    view.table().vm.$emit('update:checkedRowKeys', ['product-a'])
    await flushPromises()
    expect(view.preview().props('product').id).toBe('product-a')

    view.auth.activeTeamId = 'team-b'
    await nextTick()
    expect(view.preview().exists()).toBe(false)
    await flushPromises()

    expect(view.table().props('data')[0].id).toBe('product-b')
    expect(view.table().props('checkedRowKeys')).toEqual([])
    expect(view.preview().props('product')).toBeNull()
    expect(vi.mocked(second.list).mock.calls.at(-1)?.[0].groupId).toBe(
      'group-b',
    )
    expect(
      vi
        .mocked(second.list)
        .mock.calls.some(([query]) => query.groupId === 'group-a'),
    ).toBe(false)
    view.wrapper.unmount()
  })

  it('rejects late list and detail responses from the previous scope', async () => {
    const oldList = deferred<ProductLibraryPage>()
    const oldDetail = deferred<LibraryProduct>()
    const oldExport = deferred<{ fileName: string; content: string }>()
    const first = service('a', {
      list: vi.fn().mockReturnValue(oldList.promise),
      detail: vi.fn().mockReturnValue(oldDetail.promise),
      exportSingle: vi.fn().mockReturnValue(oldExport.promise),
    })
    const second = service('b')
    const view = render([first, second])
    await flushPromises()
    void view.open(product('product-a', null))
    void view.exportProduct(product('product-a', null))

    view.auth.activeTeamId = 'team-b'
    await flushPromises()
    expect(view.actions(product('product-b', null))[1]!.props!.disabled).toBe(
      false,
    )
    oldList.resolve(page(product('product-a', null)))
    oldDetail.resolve(product('product-a', null))
    oldExport.resolve({ fileName: 'source-product-a.txt', content: '{}' })
    await flushPromises()

    expect(view.table().props('data')[0].id).toBe('product-b')
    expect(view.preview().props('product')).toBeNull()
    expect(mocks.message.success).not.toHaveBeenCalledWith('商品 UU 资料已下载')
    view.wrapper.unmount()
  })
})
