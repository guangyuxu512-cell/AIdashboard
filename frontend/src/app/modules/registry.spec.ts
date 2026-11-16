import { describe, expect, it } from 'vitest'

import {
  getModuleAccessCode,
  getModuleAccessOptions,
  getModuleDefinition,
  getNavigationEntries,
  getNavigationModules,
  MODULE_REGISTRY,
} from './registry'

describe('execution-layer navigation', () => {
  it('removes retired AI and product-library modules and hides shop management', () => {
    expect(getModuleDefinition('ai-workbench')).toBeUndefined()
    expect(getModuleDefinition('product-library')).toBeUndefined()
    expect(getModuleDefinition('shop')).toMatchObject({ navigationVisible: false })
    const visible = getNavigationModules().map((module) => module.moduleCode)
    expect(visible).not.toContain('shop')
    expect(visible).not.toContain('ai-workbench')
    expect(visible).not.toContain('product-library')
    expect(visible).toEqual(expect.arrayContaining(['device', 'task', 'schedule', 'product-selection']))
  })

  it('retains device, task, schedule and parameter-preset navigation', () => {
    const automation = getNavigationEntries().find(
      (entry) => entry.type === 'group' && entry.groupCode === 'automation',
    )
    expect(automation?.type === 'group' && automation.children.map((item) => item.moduleCode))
      .toEqual(['device', 'task', 'schedule', 'parameter-preset'])
    expect(getModuleAccessCode(getModuleDefinition('parameter-preset')!)).toBe('device')
  })

  it('retains selection and the operating dashboard under their existing grants', () => {
    const selection = getNavigationEntries(MODULE_REGISTRY, {
      allowedModuleCodes: new Set(['product-selection']),
    })
    expect(selection).toMatchObject([{
      type: 'group', groupCode: 'product-center',
      children: [{ moduleCode: 'product-selection' }],
    }])
    expect(getModuleAccessCode(getModuleDefinition('operating-dashboard')!)).toBe('shop')
    expect(getNavigationModules(MODULE_REGISTRY, {
      allowedModuleCodes: new Set(['shop']),
    }).map((item) => item.moduleCode)).toEqual(['operating-dashboard', 'product-data'])
  })

  it('retains the asset grant without exposing a material-center menu', () => {
    expect(getModuleDefinition('asset')).toMatchObject({ enabled: true, navigationVisible: false })
    expect(getModuleAccessOptions()).toContainEqual({ value: 'asset', label: '资料库' })
    expect(getModuleAccessOptions().map((option) => option.value)).not.toContain('ai-workbench')
    expect(getNavigationModules(MODULE_REGISTRY, {
      allowedModuleCodes: new Set(['asset']),
    })).toEqual([])
  })
})
