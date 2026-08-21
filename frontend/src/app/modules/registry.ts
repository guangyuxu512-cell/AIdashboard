import { Blocks, Monitor, Store } from '@lucide/vue'
import type { Component } from 'vue'

export type ModuleNavigationGroup = 'development' | 'management'

export interface ModuleDefinition<Code extends string = string> {
  moduleCode: Code
  moduleName: string
  navigationGroup: ModuleNavigationGroup
  routeName: string
  routePath: string
  icon: Component
  enabled: boolean
  permissionCode: string | null
  order: number
}

/** App module navigation and metadata have one code-owned source of truth. */
export const MODULE_REGISTRY = [
  {
    moduleCode: 'foundation',
    moduleName: 'UI 基础设施',
    navigationGroup: 'development',
    routeName: 'home',
    routePath: '/',
    icon: Blocks,
    enabled: true,
    permissionCode: null,
    order: 10,
  },
  {
    moduleCode: 'shop',
    moduleName: '店铺中心',
    navigationGroup: 'management',
    routeName: 'shops',
    routePath: '/shops',
    icon: Store,
    enabled: true,
    permissionCode: null,
    order: 20,
  },
  {
    moduleCode: 'device',
    moduleName: '设备中心',
    navigationGroup: 'management',
    routeName: 'devices',
    routePath: '/devices',
    icon: Monitor,
    enabled: true,
    permissionCode: null,
    order: 30,
  },
] as const satisfies ReadonlyArray<ModuleDefinition>

export type ModuleCode = (typeof MODULE_REGISTRY)[number]['moduleCode']

export function getModuleDefinition<Code extends string>(
  moduleCode: Code,
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
): ModuleDefinition<Code> | undefined {
  return registry.find((module) => module.moduleCode === moduleCode) as
    | ModuleDefinition<Code>
    | undefined
}

export function requireModuleDefinition(
  moduleCode: ModuleCode,
): (typeof MODULE_REGISTRY)[number] {
  const definition = MODULE_REGISTRY.find(
    (module) => module.moduleCode === moduleCode,
  )
  if (!definition) {
    throw new Error(`Module is not registered: ${moduleCode}`)
  }
  return definition
}

export function getNavigationModules(
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
  options: { includeDevelopment?: boolean } = {},
): ModuleDefinition[] {
  return registry
    .filter(
      (module) =>
        module.enabled &&
        (options.includeDevelopment ||
          module.navigationGroup !== 'development'),
    )
    .sort((left, right) => left.order - right.order)
}
