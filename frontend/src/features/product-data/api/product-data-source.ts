import type { ApiMode } from '@/shared/api'
import type { ProductDataSource } from '../model/types'

export const PRODUCT_DATA_UNAVAILABLE = '商品数据接口尚未接入'
export function createUnavailableProductDataSource(): ProductDataSource {
  const unavailable = async (): Promise<never> => {
    throw new Error(PRODUCT_DATA_UNAVAILABLE)
  }
  return {
    mode: 'real',
    available: false,
    list: unavailable,
    groups: unavailable,
    saveGroup: unavailable,
    deleteGroup: unavailable,
    assignGroup: unavailable,
  }
}
export async function createProductDataSource(
  mode: ApiMode,
  previewCase?: string,
): Promise<ProductDataSource> {
  if (import.meta.env.VITE_API_MODE === 'mock' && mode === 'mock') {
    const { createMockProductDataSource } = await import('./product-data-mock')
    return createMockProductDataSource({
      mixedIds: import.meta.env.DEV && previewCase === 'mixed-ids',
      failOnce:
        import.meta.env.DEV && previewCase === 'query-error'
          ? 'list'
          : undefined,
    })
  }
  return createUnavailableProductDataSource()
}
