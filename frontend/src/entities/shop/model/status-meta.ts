import type { StatusTone } from '@/shared/components/StatusTag.vue'

import type { ShopEnabledStatus } from './types'

export interface ShopStatusMeta {
  label: string
  tone: StatusTone
}

export const SHOP_ENABLED_STATUS_META = {
  enabled: { label: '已启用', tone: 'success' },
  disabled: { label: '已停用', tone: 'neutral' },
} satisfies Record<ShopEnabledStatus, ShopStatusMeta>
