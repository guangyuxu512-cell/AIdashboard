import type { StatusTone } from '@/shared/components/StatusTag.vue'

import platformAllIcon from '../assets/platform-all.svg'
import platformDouyinIcon from '../assets/platform-douyin.svg'
import platformPddIcon from '../assets/platform-pdd.svg'
import platformTaobaoIcon from '../assets/platform-taobao.svg'
import platformWechatChannelsIcon from '../assets/platform-wechat-channels.svg'
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
  {
    value: 'taobao',
    label: '淘宝',
    icon: platformTaobaoIcon,
    iconAlt: '淘宝平台图标',
  },
  {
    value: 'wechat_channels',
    label: '视频号',
    icon: platformWechatChannelsIcon,
    iconAlt: '视频号平台图标',
  },
] satisfies ReadonlyArray<{
  value: ShopPlatformFilter
  label: string
  icon: string
  iconAlt: string
}>

/** 前端 V3 分组占位文案；当前没有 Group 领域或持久化契约。 */
export const SHOP_UNASSIGNED_GROUP_LABEL = '未分组'

export const SHOP_ENABLED_STATUS_META = {
  enabled: { label: '已启用', tone: 'success' },
  disabled: { label: '已停用', tone: 'neutral' },
} satisfies Record<ShopEnabledStatus, ShopStatusMeta>
