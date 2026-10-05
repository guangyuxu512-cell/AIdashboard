import { describe, expect, it } from 'vitest'

import {
  getModuleAccessCode,
  getModuleAccessOptions,
  getNavigationEntries,
  getNavigationModules,
  MODULE_REGISTRY,
  type ModuleDefinition,
} from './registry'

describe('Module Registry Lite', () => {
  it('registers only the existing application modules', () => {
    expect(MODULE_REGISTRY.map((module) => module.moduleCode)).toEqual([
      'foundation',
      'shop',
      'asset',
      'ai-workbench',
      'operating-dashboard',
      'product-selection',
      'product-library',
      'device',
      'task',
      'schedule',
      'parameter-preset',
      'settings',
    ])
  })

  it('keeps navigation order stable and development modules explicit', () => {
    expect(
      getNavigationModules(MODULE_REGISTRY, {
        includeDevelopment: false,
      }).map((module) => module.moduleCode),
    ).toEqual([
      'shop',
      'asset',
      'ai-workbench',
      'operating-dashboard',
      'product-selection',
      'product-library',
      'device',
      'task',
      'schedule',
      'parameter-preset',
      'settings',
    ])
    expect(
      getNavigationModules(MODULE_REGISTRY, { includeDevelopment: true }).map(
        (module) => module.moduleCode,
      ),
    ).toEqual([
      'foundation',
      'shop',
      'asset',
      'ai-workbench',
      'operating-dashboard',
      'product-selection',
      'product-library',
      'device',
      'task',
      'schedule',
      'parameter-preset',
      'settings',
    ])
  })

  it('builds the automation navigation group without an automation route', () => {
    const entries = getNavigationEntries()
    const automation = entries.find(
      (entry) => entry.type === 'group' && entry.groupCode === 'automation',
    )

    expect(automation).toMatchObject({
      type: 'group',
      groupName: '自动化中心',
    })
    expect(
      automation?.type === 'group'
        ? automation.children.map((module) => module.moduleCode)
        : [],
    ).toEqual(['device', 'task', 'schedule', 'parameter-preset'])
    expect(
      MODULE_REGISTRY.some(
        (module) => (module.routePath as string) === '/automation',
      ),
    ).toBe(false)
  })

  it('builds the data-center navigation group without a data-center route', () => {
    const entries = getNavigationEntries()
    const dataCenter = entries.find(
      (entry) => entry.type === 'group' && entry.groupCode === 'data-center',
    )

    expect(dataCenter).toMatchObject({
      type: 'group',
      groupName: '数据中心',
    })
    expect(
      dataCenter?.type === 'group'
        ? dataCenter.children.map((module) => module.moduleCode)
        : [],
    ).toEqual(['operating-dashboard'])
    expect(
      MODULE_REGISTRY.some(
        (module) => (module.routePath as string) === '/data-center',
      ),
    ).toBe(false)
  })

  it('registers exactly two product routes and requires each own grant', () => {
    const product = getNavigationEntries().find(
      (entry) => entry.type === 'group' && entry.groupCode === 'product-center',
    )
    expect(
      product?.type === 'group'
        ? product.children.map((child) => child.routePath)
        : [],
    ).toEqual(['/product-selection', '/products'])
    for (const code of ['product-selection', 'product-library']) {
      const entries = getNavigationEntries(MODULE_REGISTRY, {
        allowedModuleCodes: new Set([code]),
      })
      expect(entries).toHaveLength(1)
      expect(entries[0]).toMatchObject({
        type: 'group',
        groupCode: 'product-center',
        children: [{ moduleCode: code }],
      })
    }
    expect(
      getNavigationEntries(MODULE_REGISTRY, {
        allowedModuleCodes: new Set(['shop']),
      }).some(
        (entry) =>
          entry.type === 'group' && entry.groupCode === 'product-center',
      ),
    ).toBe(false)
  })

  it('does not expose disabled modules', () => {
    const disabledDevice: ModuleDefinition = {
      ...MODULE_REGISTRY.find((module) => module.moduleCode === 'device')!,
      enabled: false,
    }

    expect(
      getNavigationModules([MODULE_REGISTRY[1], disabledDevice]).map(
        (module) => module.moduleCode,
      ),
    ).toEqual(['shop'])
  })

  it('keeps permission metadata explicit without inventing permission codes', () => {
    expect(
      Object.fromEntries(
        MODULE_REGISTRY.map((module) => [
          module.moduleCode,
          module.permissionCode,
        ]),
      ),
    ).toEqual({
      foundation: null,
      shop: null,
      asset: null,
      'ai-workbench': null,
      'operating-dashboard': null,
      'product-selection': null,
      'product-library': null,
      device: null,
      task: null,
      schedule: null,
      'parameter-preset': null,
      settings: null,
    })
  })

  it('uses the existing Device permission for the distinct parameter preset route', () => {
    const parameterPreset = MODULE_REGISTRY.find(
      (module) => module.moduleCode === 'parameter-preset',
    )!

    expect(parameterPreset.accessModuleCode).toBe('device')
    expect(getModuleAccessCode(parameterPreset)).toBe('device')
    expect(
      getNavigationModules(MODULE_REGISTRY, {
        allowedModuleCodes: new Set(['device']),
      }).map((module) => module.moduleCode),
    ).toEqual(['device', 'parameter-preset'])
  })

  it('uses the existing Shop permission for the UI-only operating dashboard route', () => {
    const dashboard = MODULE_REGISTRY.find(
      (module) => module.moduleCode === 'operating-dashboard',
    )!

    expect(dashboard.accessModuleCode).toBe('shop')
    expect(getModuleAccessCode(dashboard)).toBe('shop')
    expect(
      getNavigationModules(MODULE_REGISTRY, {
        allowedModuleCodes: new Set(['shop']),
      }).map((module) => module.moduleCode),
    ).toEqual(['shop', 'operating-dashboard'])
  })

  it('derives personnel module authorization choices and navigation from the same registry', () => {
    expect(getModuleAccessOptions().map((option) => option.value)).toEqual([
      'shop',
      'asset',
      'ai-workbench',
      'product-selection',
      'product-library',
      'device',
      'task',
      'schedule',
      'settings',
    ])
    expect(
      getNavigationModules(MODULE_REGISTRY, {
        allowedModuleCodes: new Set(['asset', 'settings']),
      }).map((module) => module.moduleCode),
    ).toEqual(['asset', 'settings'])
  })
})
