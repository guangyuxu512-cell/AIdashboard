import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

import { installAuthGuard } from '@/app/router/auth-guard'
import type {
  CurrentModuleAccess,
  HumanAuthDataSource,
  HumanTeamMembership,
} from '@/entities/human-auth'
import { configureAuthEffects, useAuthStore } from '@/stores/auth'
import type { LibraryProduct, ProductLibraryService } from '../model/contracts'
import ProductLibraryWorkspace from './ProductLibraryWorkspace.vue'

const mocks = vi.hoisted(() => ({
  service: vi.fn(),
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
vi.mock('naive-ui', async (original) => ({
  ...(await original<typeof import('naive-ui')>()),
  useMessage: () => mocks.message,
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((accept) => {
    resolve = accept
  })
  return { promise, resolve }
}

function product(id: string): LibraryProduct {
  return {
    id,
    productId: `source-${id}`,
    platform: 'douyin',
    title: id,
    groupId: null,
    groupName: null,
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

function serviceFor(item: LibraryProduct): ProductLibraryService {
  const unsupported = vi.fn().mockRejectedValue(new Error('不可用'))
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
    groups: vi.fn().mockResolvedValue([]),
    list: vi.fn().mockResolvedValue({
      items: [item],
      total: 1,
      page: 1,
      pageSize: 20,
      categories: [],
    }),
    detail: vi.fn().mockResolvedValue(item),
    saveEdit: unsupported,
    createGroup: unsupported,
    moveToGroup: unsupported,
    remove: unsupported,
    recollect: unsupported,
    exportSingle: vi.fn(),
  }
}

const access: CurrentModuleAccess = {
  moduleCodes: ['product-library'],
  isAccessAdministrator: true,
  isSuperAccount: true,
}

const team: HumanTeamMembership = {
  membershipId: 'membership-team-a',
  teamId: 'team-a',
  teamName: 'Team A',
  teamEnabled: true,
  membershipEnabled: true,
  roleCode: 'member',
  dataScope: 'team',
}

const passthrough = {
  template:
    '<div><slot /><slot name="actions" /><slot name="primary-action" /></div>',
}

describe('product library real team switch authorization timing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    configureAuthEffects({
      onTeamChanged: () => undefined,
      onAuthCleared: () => undefined,
      onAuthRestoreRejected: () => undefined,
    })
  })

  it('keeps the product-library route until the new team grant is ready', async () => {
    const selectedAccess = deferred<CurrentModuleAccess>()
    const source: HumanAuthDataSource = {
      login: vi.fn(),
      logout: vi.fn(),
      getCurrentUser: vi.fn().mockResolvedValue({
        userId: 'super-user',
        displayName: '超级管理员',
      }),
      listMyTeams: vi.fn().mockResolvedValue([team]),
      getCurrentModuleAccess: vi
        .fn()
        .mockResolvedValueOnce(access)
        .mockReturnValueOnce(selectedAccess.promise),
    }
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore(pinia)
    auth.setDataSource(source)
    const requestedScopes: Array<string | null> = []
    const globalProduct = product('global-product')
    const teamProduct = product('team-product')
    mocks.service.mockImplementation(async () => {
      requestedScopes.push(auth.activeTeamId)
      return serviceFor(
        auth.activeTeamId === null ? globalProduct : teamProduct,
      )
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/login',
          name: 'login',
          component: { template: '<div />' },
          meta: { public: true },
        },
        {
          path: '/permission-denied',
          name: 'permission-denied',
          component: { template: '<div>denied</div>' },
        },
        {
          path: '/products',
          name: 'product-library',
          component: ProductLibraryWorkspace,
          meta: { moduleCode: 'product-library' },
        },
      ],
    })
    installAuthGuard(router, pinia)
    await router.push('/products?productId=source-global-product')
    await router.isReady()

    const wrapper = mount(
      {
        components: { RouterView },
        template: '<RouterView />',
      },
      {
        global: {
          plugins: [pinia, router],
          stubs: {
            ProductPreviewDialog: {
              name: 'ProductPreviewDialog',
              props: ['show', 'product'],
              template:
                '<div class="preview" v-if="show">{{ product?.id }}</div>',
            },
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
              props: ['data'],
              template:
                '<div><span v-for="row in data" :key="row.id">{{ row.id }}</span></div>',
            },
            PaginationBar: true,
          },
        },
      },
    )
    await flushPromises()
    expect(wrapper.get('.preview').text()).toBe('global-product')
    expect(router.currentRoute.value.name).toBe('product-library')

    const teamSelection = auth.selectTeam('team-a')
    await nextTick()

    expect(wrapper.find('.preview').exists()).toBe(false)
    expect(router.currentRoute.value.name).toBe('product-library')
    expect(requestedScopes).toEqual([null])

    selectedAccess.resolve(access)
    await teamSelection
    await flushPromises()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('product-library')
    expect(router.currentRoute.value.query.productId).toBeUndefined()
    expect(wrapper.text()).toContain('team-product')
    expect(requestedScopes).toEqual([null, 'team-a'])
    expect(source.getCurrentModuleAccess).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
