import type { ShopListItemViewModel } from './types'

export interface ShopExecutionDeviceSummary {
  count: number
  label: string
  names: string[]
}

/** 将普通执行资格绑定映射为列表摘要。 */
export function getShopExecutionDeviceSummary(
  shop: ShopListItemViewModel,
): ShopExecutionDeviceSummary {
  const names = shop.executionDeviceNames

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
