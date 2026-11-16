import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'

export function resolveSafeRedirect(value: unknown): string | null {
  if (
    typeof value === 'string' &&
    value.startsWith('/') &&
    !value.startsWith('//') &&
    !value.startsWith('/login')
  ) {
    return value
  }
  return null
}

export function resolveAuthenticatedStartRoute(
  allowedModuleCodes: ReadonlySet<string>,
): string {
  if (allowedModuleCodes.has('device')) return '/devices'
  if (allowedModuleCodes.has('task')) return '/tasks'
  if (allowedModuleCodes.has('schedule')) return '/schedules'
  if (allowedModuleCodes.has('shop')) return '/shops'
  return '/me'
}

export function resolvePostAuthRoute(
  redirect: unknown,
  allowedModuleCodes: ReadonlySet<string>,
): string {
  return (
    resolveSafeRedirect(redirect) ??
    resolveAuthenticatedStartRoute(allowedModuleCodes)
  )
}

export function isLoginRouteName(name: unknown): boolean {
  return name === MOBILE_ROUTE_NAMES.login
}
