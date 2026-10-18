import type { ProductDataQuery } from '../model/types'
export const productDataKeys = {
  all: (contextKey: string) => ['product-data', contextKey] as const,
  list: (contextKey: string, query: ProductDataQuery) =>
    ['product-data', contextKey, 'list', query] as const,
  groups: (contextKey: string, shopId: string | null) =>
    ['product-data', contextKey, 'groups', shopId] as const,
}
