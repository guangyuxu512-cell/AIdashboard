import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_COLUMNS,
  type ProductColumnId,
} from './types'

const prefix = 'control-center.product-data.columns.v1.'
export function normalizeProductColumns(value: unknown): ProductColumnId[] {
  if (!Array.isArray(value)) return [...DEFAULT_PRODUCT_COLUMNS]
  const known = new Set<string>(PRODUCT_COLUMNS.map((column) => column.id))
  const columns = [
    ...new Set(
      value.filter(
        (id): id is ProductColumnId => typeof id === 'string' && known.has(id),
      ),
    ),
  ]
  return columns.length ? columns : [...DEFAULT_PRODUCT_COLUMNS]
}
export function readProductColumns(userId: string | null): ProductColumnId[] {
  if (!userId) return [...DEFAULT_PRODUCT_COLUMNS]
  try {
    const stored = window.localStorage.getItem(prefix + userId)
    return stored
      ? normalizeProductColumns(JSON.parse(stored))
      : [...DEFAULT_PRODUCT_COLUMNS]
  } catch {
    return [...DEFAULT_PRODUCT_COLUMNS]
  }
}
export function saveProductColumns(
  userId: string | null,
  columns: ProductColumnId[],
): void {
  if (!userId) throw new Error('请登录后保存个人字段配置')
  if (!columns.length) throw new Error('至少选择一个字段')
  window.localStorage.setItem(
    prefix + userId,
    JSON.stringify(normalizeProductColumns(columns)),
  )
}
