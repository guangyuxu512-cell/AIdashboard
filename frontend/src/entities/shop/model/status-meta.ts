import type { StatusTone } from '@/shared/components/StatusTag.vue'

import type {
  ShopAutomationStatus,
  ShopConfigurationStatus,
  ShopEnabledStatus,
  ShopPlatform,
  ShopSessionStatus,
} from './types'

export interface ShopStatusMeta {
  label: string
  tone: StatusTone
}

export const SHOP_PLATFORM_META = {
  douyin: { label: '抖音' },
  taobao: { label: '淘宝' },
  pdd: { label: '拼多多' },
  jd: { label: '京东' },
} satisfies Record<ShopPlatform, { label: string }>

export const SHOP_ENABLED_STATUS_META = {
  enabled: { label: '已启用', tone: 'success' },
  disabled: { label: '已停用', tone: 'neutral' },
} satisfies Record<ShopEnabledStatus, ShopStatusMeta>

export const SHOP_SESSION_STATUS_META = {
  normal: { label: '正常', tone: 'success' },
  warning: { label: '异常', tone: 'error' },
  not_configured: { label: '未配置', tone: 'neutral' },
  unavailable: { label: '未接入', tone: 'neutral' },
} satisfies Record<ShopSessionStatus, ShopStatusMeta>

export const SHOP_AUTOMATION_STATUS_META = {
  running: { label: '运行中', tone: 'info' },
  idle: { label: '空闲', tone: 'neutral' },
  paused: { label: '已暂停', tone: 'warning' },
  unavailable: { label: '未接入', tone: 'neutral' },
} satisfies Record<ShopAutomationStatus, ShopStatusMeta>

export const SHOP_CONFIGURATION_STATUS_META = {
  configured: { label: '已配置', tone: 'success' },
  not_configured: { label: '未配置', tone: 'neutral' },
  unavailable: { label: '未接入', tone: 'neutral' },
} satisfies Record<ShopConfigurationStatus, ShopStatusMeta>
