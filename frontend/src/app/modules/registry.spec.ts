import { describe, expect, it } from 'vitest'

import {
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
      'device',
      'task',
      'schedule',
      'settings',
    ])
  })

  it('keeps navigation order stable and development modules explicit', () => {
    expect(getNavigationModules().map((module) => module.moduleCode)).toEqual([
      'shop',
      'device',
      'task',
      'schedule',
      'settings',
    ])
    expect(
      getNavigationModules(MODULE_REGISTRY, { includeDevelopment: true }).map(
        (module) => module.moduleCode,
      ),
    ).toEqual(['foundation', 'shop', 'device', 'task', 'schedule', 'settings'])
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
    ).toEqual(['device', 'task', 'schedule'])
    expect(
      MODULE_REGISTRY.some(
        (module) => (module.routePath as string) === '/automation',
      ),
    ).toBe(false)
  })

  it('does not expose disabled modules', () => {
    const disabledDevice: ModuleDefinition = {
      ...MODULE_REGISTRY[2],
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
      device: null,
      task: null,
      schedule: null,
      settings: null,
    })
  })
})
