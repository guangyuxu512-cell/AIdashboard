import type { ShopListItemViewModel } from './types'

export interface ShopExecutionDeviceSummary {
  count: number
  label: string
  names: string[]
}

/**
 * 将现有主/备用绑定映射为列表摘要。只消费 View Model，不扩展 Backend 契约。
 */
export function getShopExecutionDeviceSummary(
  shop: ShopListItemViewModel,
): ShopExecutionDeviceSummary {
  const names = [
    ...(shop.executionDeviceName ? [shop.executionDeviceName] : []),
    ...shop.backupDeviceNames,
  ]

  return {
    count: names.length,
    names,
    label:
      names.length === 0
        ? '未分配'
        : names.length === 1
          ? names[0]
          : `${names[0]} +${names.length - 1}`,
  }
}
