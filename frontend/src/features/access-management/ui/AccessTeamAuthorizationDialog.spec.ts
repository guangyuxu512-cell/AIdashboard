import { shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AccessTeamAuthorizationDialog from './AccessTeamAuthorizationDialog.vue'

const mocks = vi.hoisted(() => ({
  deviceParams: null as { value: unknown } | null,
  shopParams: null as { value: unknown } | null,
}))

const emptyQuery = () => ({
  data: ref({ items: [], total: 0, page: 1, pageSize: 100 }),
  isPending: ref(false),
})

vi.mock('@/app/modules/registry', () => ({
  getModuleAccessOptions: () => [],
}))

vi.mock('@/entities/access-management', () => ({
  useAccessTeamAuthorizationQuery: () => ({
    data: ref({ moduleCodes: [], deviceIds: [], shopIds: [] }),
    isPending: ref(false),
  }),
}))

vi.mock('@/entities/device', () => ({
  useDeviceListQuery: (params: { value: unknown }) => {
    mocks.deviceParams = params
    return emptyQuery()
  },
}))

vi.mock('@/entities/shop', () => ({
  useShopListQuery: (params: { value: unknown }) => {
    mocks.shopParams = params
    return emptyQuery()
  },
}))

beforeEach(() => {
  mocks.deviceParams = null
  mocks.shopParams = null
})

describe('AccessTeamAuthorizationDialog', () => {
  it('requests the largest resource page accepted by the shared API contract', () => {
    shallowMount(AccessTeamAuthorizationDialog, {
      props: {
        show: true,
        team: {
          teamId: 'team-a',
          name: '团队 A',
          enabled: true,
          createdAt: '2026-09-20T00:00:00Z',
          updatedAt: '2026-09-20T00:00:00Z',
        },
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(mocks.deviceParams).not.toBeNull()
    expect(mocks.shopParams).not.toBeNull()
    expect(mocks.deviceParams?.value).toMatchObject({ page: 1, pageSize: 100 })
    expect(mocks.shopParams?.value).toMatchObject({ page: 1, pageSize: 100 })
  })
})
