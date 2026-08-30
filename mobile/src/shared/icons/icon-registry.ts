import type { Component } from 'vue'

import DevicePrimaryGlyph from './glyphs/DevicePrimaryGlyph.vue'
import NotificationBellGlyph from './glyphs/NotificationBellGlyph.vue'
import TaskPrimaryGlyph from './glyphs/TaskPrimaryGlyph.vue'
import ThemeMoonGlyph from './glyphs/ThemeMoonGlyph.vue'
import ThemeSunGlyph from './glyphs/ThemeSunGlyph.vue'

export const MOBILE_ICON_ROLES = [
  'primary',
  'runtime',
  'capability',
  'status',
  'navigation',
  'action',
] as const

export type MobileIconRole = (typeof MOBILE_ICON_ROLES)[number]
export type MobileIconTone =
  'primary' | 'success' | 'warning' | 'danger' | 'muted' | 'secondary'

type MobileIconSource =
  | { kind: 'vant'; name: string }
  | { kind: 'asset'; src: string }
  | { kind: 'component'; component: Component }

export interface MobileIconDefinition {
  label: string
  role: MobileIconRole
  source: MobileIconSource
  tone?: MobileIconTone
}

/**
 * 唯一的 Mobile 图标语义入口：业务代码只使用 key，不感知 Vant 名称或静态资源路径。
 */
export const MOBILE_ICON_REGISTRY = {
  fallback: {
    label: '未知图标',
    role: 'action',
    source: { kind: 'vant', name: 'question-o' },
    tone: 'muted',
  },
  device: {
    label: '设备',
    role: 'primary',
    source: { kind: 'component', component: DevicePrimaryGlyph },
    tone: 'primary',
  },
  task: {
    label: '任务',
    role: 'primary',
    source: { kind: 'component', component: TaskPrimaryGlyph },
    tone: 'primary',
  },
  'runtime-device': {
    label: '设备运行端',
    role: 'runtime',
    source: { kind: 'component', component: DevicePrimaryGlyph },
  },
  automation: {
    label: '自动化账号',
    role: 'runtime',
    source: { kind: 'vant', name: 'manager-o' },
  },
  application: {
    label: '应用能力',
    role: 'capability',
    source: { kind: 'vant', name: 'apps-o' },
  },
  skill: {
    label: '业务技能',
    role: 'capability',
    source: { kind: 'vant', name: 'setting-o' },
  },
  online: {
    label: '在线',
    role: 'status',
    source: { kind: 'vant', name: 'passed' },
    tone: 'success',
  },
  running: {
    label: '运行中',
    role: 'status',
    source: { kind: 'vant', name: 'play-circle-o' },
    tone: 'primary',
  },
  offline: {
    label: '离线',
    role: 'status',
    source: { kind: 'vant', name: 'clear' },
    tone: 'muted',
  },
  pending: {
    label: '待执行',
    role: 'status',
    source: { kind: 'vant', name: 'clock-o' },
    tone: 'warning',
  },
  success: {
    label: '成功',
    role: 'status',
    source: { kind: 'vant', name: 'success' },
    tone: 'success',
  },
  failed: {
    label: '失败',
    role: 'status',
    source: { kind: 'vant', name: 'failure' },
    tone: 'danger',
  },
  warning: {
    label: '警告',
    role: 'status',
    source: { kind: 'vant', name: 'warning-o' },
    tone: 'warning',
  },
  'device-nav': {
    label: '设备导航',
    role: 'navigation',
    source: { kind: 'vant', name: 'desktop-o' },
  },
  'task-nav': {
    label: '任务导航',
    role: 'navigation',
    source: { kind: 'vant', name: 'todo-list-o' },
  },
  'schedule-nav': {
    label: '计划导航',
    role: 'navigation',
    source: { kind: 'vant', name: 'calendar-o' },
  },
  'shop-nav': {
    label: '店铺导航',
    role: 'navigation',
    source: { kind: 'vant', name: 'shop-o' },
  },
  'profile-nav': {
    label: '我的导航',
    role: 'navigation',
    source: { kind: 'vant', name: 'user-o' },
  },
  'theme-light': {
    label: '切换到浅色主题',
    role: 'action',
    source: { kind: 'component', component: ThemeSunGlyph },
  },
  'theme-dark': {
    label: '切换到深色主题',
    role: 'action',
    source: { kind: 'component', component: ThemeMoonGlyph },
  },
  'notification-bell': {
    label: '通知',
    role: 'action',
    source: { kind: 'component', component: NotificationBellGlyph },
  },
  filter: {
    label: '筛选',
    role: 'action',
    source: { kind: 'vant', name: 'filter-o' },
  },
  'arrow-down': {
    label: '展开选择',
    role: 'action',
    source: { kind: 'vant', name: 'arrow-down' },
  },
  refresh: {
    label: '刷新',
    role: 'action',
    source: { kind: 'vant', name: 'replay' },
  },
  back: {
    label: '返回',
    role: 'action',
    source: { kind: 'vant', name: 'arrow-left' },
  },
  'chevron-right': {
    label: '查看详情',
    role: 'action',
    source: { kind: 'vant', name: 'arrow' },
  },
  close: {
    label: '关闭',
    role: 'action',
    source: { kind: 'vant', name: 'cross' },
  },
  configure: {
    label: '配置',
    role: 'action',
    source: { kind: 'vant', name: 'setting-o' },
  },
  run: {
    label: '运行',
    role: 'action',
    source: { kind: 'vant', name: 'play' },
  },
} as const satisfies Record<string, MobileIconDefinition>

export type MobileIconName = keyof typeof MOBILE_ICON_REGISTRY

const warnedUnknownIconNames = new Set<string>()

export function isMobileIconName(name: string): name is MobileIconName {
  return Object.hasOwn(MOBILE_ICON_REGISTRY, name)
}

export function resolveMobileIcon(name: string): MobileIconDefinition {
  if (isMobileIconName(name)) return MOBILE_ICON_REGISTRY[name]

  if (import.meta.env.DEV && !warnedUnknownIconNames.has(name)) {
    warnedUnknownIconNames.add(name)
    console.warn(`[MobileIcon] 未注册图标：${name}`)
  }

  return MOBILE_ICON_REGISTRY.fallback
}

export const MOBILE_ICON_GALLERY_GROUPS = [
  { label: '主业务', names: ['device', 'task'] },
  { label: '运行摘要', names: ['runtime-device', 'automation'] },
  { label: '能力', names: ['application', 'skill'] },
  {
    label: '状态',
    names: ['online', 'running', 'offline', 'pending', 'success', 'failed'],
  },
  {
    label: '导航',
    names: [
      'device-nav',
      'task-nav',
      'schedule-nav',
      'shop-nav',
      'profile-nav',
    ],
  },
  {
    label: '操作',
    names: [
      'theme-light',
      'theme-dark',
      'notification-bell',
      'filter',
      'arrow-down',
      'refresh',
      'back',
      'chevron-right',
      'close',
    ],
  },
] as const satisfies ReadonlyArray<{
  label: string
  names: readonly MobileIconName[]
}>
