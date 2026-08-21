import { describe, expect, it } from 'vitest'

import {
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
      'settings',
    ])
  })

  it('keeps navigation order stable and development modules explicit', () => {
    expect(getNavigationModules().map((module) => module.moduleCode)).toEqual([
      'shop',
      'device',
      'settings',
    ])
    expect(
      getNavigationModules(MODULE_REGISTRY, { includeDevelopment: true }).map(
        (module) => module.moduleCode,
      ),
    ).toEqual(['foundation', 'shop', 'device', 'settings'])
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
      settings: null,
    })
  })
})
