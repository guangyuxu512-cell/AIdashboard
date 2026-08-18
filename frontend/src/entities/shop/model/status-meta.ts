import type { StatusTone } from '@/shared/components/StatusTag.vue'

import platformAllIcon from '../assets/platform-all.svg'
import platformDouyinIcon from '../assets/platform-douyin.svg'
import platformPddIcon from '../assets/platform-pdd.svg'
import type {
  ShopEnabledStatus,
  ShopPlatform,
  ShopPlatformFilter,
} from './types'

export interface ShopStatusMeta {
  label: string
  tone: StatusTone
}

export interface ShopPlatformMeta {
  value: ShopPlatform
  label: string
  icon: string
  iconAlt: string
}

export const SHOP_PLATFORM_META = {
  douyin: {
    value: 'douyin',
    label: '抖店',
    icon: platformDouyinIcon,
    iconAlt: '抖店平台图标',
  },
  pdd: {
    value: 'pdd',
    label: '拼多多',
    icon: platformPddIcon,
    iconAlt: '拼多多平台图标',
  },
} satisfies Record<ShopPlatform, ShopPlatformMeta>

export const SHOP_PLATFORM_NAV_ITEMS = [
  {
    value: 'all',
    label: '全部平台',
    icon: platformAllIcon,
    iconAlt: '全部平台图标',
  },
  SHOP_PLATFORM_META.douyin,
  SHOP_PLATFORM_META.pdd,
] satisfies ReadonlyArray<{
  value: ShopPlatformFilter
  label: string
  icon: string
  iconAlt: string
}>

export const SHOP_ENABLED_STATUS_META = {
  enabled: { label: '已启用', tone: 'success' },
  disabled: { label: '已停用', tone: 'neutral' },
} satisfies Record<ShopEnabledStatus, ShopStatusMeta>
