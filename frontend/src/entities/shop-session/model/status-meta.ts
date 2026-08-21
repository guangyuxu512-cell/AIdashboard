import type { StatusTone } from '@/shared/components/StatusTag.vue'

import type { ShopSessionStatus } from './types'

export interface ShopSessionStatusMeta {
  label: string
  tone: StatusTone
}

export const SHOP_SESSION_STATUS_META: Record<
  ShopSessionStatus,
  ShopSessionStatusMeta
> = {
  not_configured: { label: '未登录', tone: 'neutral' },
  captured: { label: '待验证', tone: 'info' },
  valid: { label: '有效', tone: 'success' },
  invalid: { label: '已失效', tone: 'error' },
  refresh_required: { label: '需要刷新', tone: 'warning' },
}
