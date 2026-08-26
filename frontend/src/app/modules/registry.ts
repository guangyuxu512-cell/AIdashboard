import {
  Blocks,
  CalendarClock,
  Images,
  ListChecks,
  Monitor,
  Settings,
  Store,
  Workflow,
} from '@lucide/vue'
import type { Component } from 'vue'

export type ModuleNavigationGroup = 'development' | 'management'
export type ModuleNavigationParent = 'automation'

export interface ModuleDefinition<Code extends string = string> {
  moduleCode: Code
  moduleName: string
  navigationGroup: ModuleNavigationGroup
  navigationParent: ModuleNavigationParent | null
  routeName: string
  routePath: string
  icon: Component
  enabled: boolean
  permissionCode: string | null
  order: number
}

export interface NavigationGroupDefinition {
  groupCode: ModuleNavigationParent
  groupName: string
  icon: Component
  order: number
}

export interface ModuleNavigationEntry extends ModuleDefinition {
  type: 'module'
}

export interface GroupNavigationEntry extends NavigationGroupDefinition {
  type: 'group'
  children: ModuleNavigationEntry[]
}

export type NavigationEntry = ModuleNavigationEntry | GroupNavigationEntry

export const NAVIGATION_GROUP_REGISTRY = [
  {
    groupCode: 'automation',
    groupName: '自动化中心',
    icon: Workflow,
    order: 30,
  },
] as const satisfies ReadonlyArray<NavigationGroupDefinition>

/** App module navigation and metadata have one code-owned source of truth. */
export const MODULE_REGISTRY = [
  {
    moduleCode: 'foundation',
    moduleName: 'UI 基础设施',
    navigationGroup: 'development',
    navigationParent: null,
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
    navigationParent: null,
    routeName: 'shops',
    routePath: '/shops',
    icon: Store,
    enabled: true,
    permissionCode: null,
    order: 20,
  },
  {
    moduleCode: 'asset',
    moduleName: '资料库',
    navigationGroup: 'management',
    navigationParent: null,
    routeName: 'assets',
    routePath: '/assets',
    icon: Images,
    enabled: true,
    permissionCode: null,
    order: 25,
  },
  {
    moduleCode: 'device',
    moduleName: '设备中心',
    navigationGroup: 'management',
    navigationParent: 'automation',
    routeName: 'devices',
    routePath: '/devices',
    icon: Monitor,
    enabled: true,
    permissionCode: null,
    order: 31,
  },
  {
    moduleCode: 'task',
    moduleName: '任务中心',
    navigationGroup: 'management',
    navigationParent: 'automation',
    routeName: 'tasks',
    routePath: '/tasks',
    icon: ListChecks,
    enabled: true,
    permissionCode: null,
    order: 32,
  },
  {
    moduleCode: 'schedule',
    moduleName: '定时计划',
    navigationGroup: 'management',
    navigationParent: 'automation',
    routeName: 'schedules',
    routePath: '/schedules',
    icon: CalendarClock,
    enabled: true,
    permissionCode: null,
    order: 33,
  },
  {
    moduleCode: 'settings',
    moduleName: '系统设置',
    navigationGroup: 'management',
    navigationParent: null,
    routeName: 'notification-settings',
    routePath: '/settings/notifications',
    icon: Settings,
    enabled: true,
    permissionCode: null,
    order: 40,
  },
] as const satisfies ReadonlyArray<ModuleDefinition>

export type ModuleCode = (typeof MODULE_REGISTRY)[number]['moduleCode']

export function getModuleDefinition<Code extends string>(
  moduleCode: Code,
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
): ModuleDefinition<Code> | undefined {
  return registry.find((module) => module.moduleCode === moduleCode) as
    ModuleDefinition<Code> | undefined
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

export function getNavigationEntries(
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
  options: { includeDevelopment?: boolean } = {},
  groups: ReadonlyArray<NavigationGroupDefinition> = NAVIGATION_GROUP_REGISTRY,
): NavigationEntry[] {
  const modules = getNavigationModules(registry, options)
  const entries: NavigationEntry[] = modules
    .filter((module) => module.navigationParent === null)
    .map((module) => ({ ...module, type: 'module' }))

  for (const group of groups) {
    const children = modules
      .filter((module) => module.navigationParent === group.groupCode)
      .map((module) => ({ ...module, type: 'module' }) as ModuleNavigationEntry)
    if (children.length) entries.push({ ...group, type: 'group', children })
  }

  return entries.sort((left, right) => left.order - right.order)
}
