import {
  Blocks,
  CalendarClock,
  ChartLine,
  SlidersHorizontal,
  Images,
  ListChecks,
  Monitor,
  Package,
  Library,
  Settings,
  Sparkles,
  Store,
  Workflow,
} from '@lucide/vue'
import type { Component } from 'vue'

import { AI_WORKBENCH_ROUTES } from '@/features/ai-workbench/model/routes'

export type ModuleNavigationGroup = 'development' | 'management'
export type ModuleNavigationParent =
  'automation' | 'data-center' | 'product-center'

export interface ModuleDefinition<Code extends string = string> {
  moduleCode: Code
  /** Existing Backend permission used for this distinct UI route, if any. */
  accessModuleCode: string | null
  moduleName: string
  navigationGroup: ModuleNavigationGroup
  navigationParent: ModuleNavigationParent | null
  routeName: string
  routePath: string
  icon: Component
  enabled: boolean
  /** Sidebar visibility only; hidden modules keep routes and authorization. */
  navigationVisible?: boolean
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

export interface ModuleNavigationOptions {
  includeDevelopment?: boolean
  allowedModuleCodes?: ReadonlySet<string> | null
}

export const NAVIGATION_GROUP_REGISTRY = [
  {
    groupCode: 'data-center',
    groupName: '数据中心',
    icon: ChartLine,
    order: 28,
  },
  {
    groupCode: 'product-center',
    groupName: '商品中心',
    icon: Package,
    order: 29,
  },
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
    accessModuleCode: null,
    moduleName: 'UI 基础设施',
    navigationGroup: 'development',
    navigationParent: null,
    routeName: 'home',
    routePath: '/foundation',
    icon: Blocks,
    enabled: true,
    permissionCode: null,
    order: 10,
  },
  {
    moduleCode: 'shop',
    accessModuleCode: null,
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
    accessModuleCode: null,
    moduleName: '资料库',
    navigationGroup: 'management',
    navigationParent: null,
    routeName: 'assets',
    routePath: '/assets',
    icon: Images,
    enabled: true,
    navigationVisible: false,
    permissionCode: null,
    order: 25,
  },
  {
    moduleCode: 'ai-workbench',
    accessModuleCode: null,
    moduleName: 'AI工作台',
    navigationGroup: 'management',
    navigationParent: null,
    routeName: AI_WORKBENCH_ROUTES.generate.name,
    routePath: AI_WORKBENCH_ROUTES.generate.path,
    icon: Sparkles,
    enabled: true,
    permissionCode: null,
    order: 27,
  },
  {
    moduleCode: 'operating-dashboard',
    // V1 has no Backend data-center module or permission code. The dashboard
    // only reads the current actor's shop-scoped business data when that
    // contract exists, so it reuses the existing Shop guard.
    accessModuleCode: 'shop',
    moduleName: '经营看板',
    navigationGroup: 'management',
    navigationParent: 'data-center',
    routeName: 'operating-dashboard',
    routePath: '/operating-dashboard',
    icon: ChartLine,
    enabled: true,
    permissionCode: null,
    order: 28,
  },
  {
    moduleCode: 'product-selection',
    accessModuleCode: null,
    moduleName: '选品库',
    navigationGroup: 'management',
    navigationParent: 'product-center',
    routeName: 'product-selection',
    routePath: '/product-selection',
    icon: Library,
    enabled: true,
    permissionCode: null,
    order: 29,
  },
  {
    moduleCode: 'product-library',
    accessModuleCode: null,
    moduleName: '商品库',
    navigationGroup: 'management',
    navigationParent: 'product-center',
    routeName: 'product-library',
    routePath: '/products',
    icon: Package,
    enabled: true,
    permissionCode: null,
    order: 30,
  },
  {
    moduleCode: 'device',
    accessModuleCode: null,
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
    accessModuleCode: null,
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
    accessModuleCode: null,
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
    moduleCode: 'parameter-preset',
    // The API uses the existing Device ActorContext guard.  This does not
    // create a Backend `parameter-preset` permission or expose new data.
    accessModuleCode: 'device',
    moduleName: '参数配置',
    navigationGroup: 'management',
    navigationParent: 'automation',
    routeName: 'parameter-presets',
    routePath: '/parameter-presets',
    icon: SlidersHorizontal,
    enabled: true,
    permissionCode: null,
    order: 34,
  },
  {
    moduleCode: 'settings',
    accessModuleCode: null,
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

export function getModuleAccessCode(module: ModuleDefinition): string {
  return module.accessModuleCode ?? module.moduleCode
}

export function getNavigationModules(
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
  options: ModuleNavigationOptions = {},
): ModuleDefinition[] {
  return registry
    .filter(
      (module) =>
        module.enabled &&
        module.navigationVisible !== false &&
        (options.includeDevelopment ||
          module.navigationGroup !== 'development') &&
        (module.navigationGroup === 'development' ||
          options.allowedModuleCodes == null ||
          options.allowedModuleCodes.has(getModuleAccessCode(module))),
    )
    .sort((left, right) => left.order - right.order)
}

export function getNavigationEntries(
  registry: ReadonlyArray<ModuleDefinition> = MODULE_REGISTRY,
  options: ModuleNavigationOptions = {},
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

export function getModuleAccessOptions(): Array<{
  value: string
  label: string
}> {
  return MODULE_REGISTRY.filter(
    (module) =>
      module.enabled &&
      module.navigationGroup !== 'development' &&
      module.accessModuleCode === null,
  )
    .sort((left, right) => left.order - right.order)
    .map((module) => ({
      value: module.moduleCode,
      label: module.moduleName,
    }))
}
