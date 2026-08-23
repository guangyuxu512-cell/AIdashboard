import type { YingdaoInventoryViewModel } from '../model/types'

const applications = [
  {
    appId: 'app-fixture-product-publish',
    appName: '商品发布（Fixture）',
    versionId: '3',
  },
  {
    appId: 'app-fixture-inventory-sync',
    appName: '库存同步（Fixture）',
    versionId: '2',
  },
  {
    appId: 'app-fixture-after-sales',
    appName: '售后工单（Fixture）',
    versionId: '1',
  },
]

function inventory(
  applicationCount: number,
  overrides: Partial<YingdaoInventoryViewModel> = {},
): YingdaoInventoryViewModel {
  const expanded = Array.from({ length: applicationCount }, (_, index) => {
    const source = applications[index % applications.length]!
    return {
      ...source,
      appId: `${source.appId}-${index + 1}`,
      appName:
        index < applications.length
          ? source.appName
          : `${source.appName} ${index + 1}`,
    }
  })
  return {
    available: true,
    availabilityStatus: 'available',
    providerStatus: 'ready',
    statusReason: null,
    providerVersion: '6.3.6 (Fixture)',
    executionAvailable: true,
    executionVersion: '6.3.6',
    executionUnavailableReason: null,
    loggedIn: true,
    accountDisplay: 'GY00999',
    accountType: 'PersonalBasic',
    enterpriseAccount: false,
    applicationCount,
    applications: expanded,
    lastDiscoveredAtDisplay: '2 分钟前',
    ...overrides,
  }
}

export const YINGDAO_INVENTORY_FIXTURE_BY_DEVICE: Record<
  string,
  YingdaoInventoryViewModel | null
> = {
  'device-fixture-001': inventory(9),
  'device-fixture-002': inventory(5),
  'device-fixture-003': inventory(7),
  'device-fixture-004': inventory(0, {
    available: false,
    availabilityStatus: 'unavailable',
    loggedIn: false,
    accountDisplay: '—',
    accountType: '—',
  }),
  'device-fixture-005': null,
  'device-fixture-006': inventory(4, { accountDisplay: 'QA001' }),
  'device-fixture-007': null,
  'device-fixture-008': inventory(6),
}
