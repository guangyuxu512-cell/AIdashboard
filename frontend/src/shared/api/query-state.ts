export function hasResolvedQueryData(data: unknown): boolean {
  return data !== undefined
}

export function isInitialQueryLoading(
  isPending: boolean,
  data: unknown,
): boolean {
  return isPending && !hasResolvedQueryData(data)
}

export function isInitialQueryError(error: unknown, data: unknown): boolean {
  return Boolean(error) && !hasResolvedQueryData(data)
}
