export const DEFAULT_AUTHENTICATED_ROUTE = '/shops'

export function resolveSafeRedirect(value: unknown): string {
  if (
    typeof value === 'string' &&
    value.startsWith('/') &&
    !value.startsWith('//') &&
    !value.startsWith('/login')
  ) {
    return value
  }
  return DEFAULT_AUTHENTICATED_ROUTE
}
