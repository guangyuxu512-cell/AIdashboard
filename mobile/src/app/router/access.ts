import type { NavigationGuard, Router } from 'vue-router'

export interface RouteAccessGuards {
  authGuard?: NavigationGuard
  permissionGuard?: NavigationGuard
}

/**
 * Installs only the formal guards supplied by the future access layer.
 *
 * Registration order is intentionally fixed: authentication first, permission
 * second. The Foundation does not provide fallback identities, tokens, roles or
 * permissions, so the router bootstrap does not call this function yet.
 */
export function installRouteAccessGuards(
  router: Router,
  guards: RouteAccessGuards,
): () => void {
  const removeAuthGuard = guards.authGuard
    ? router.beforeEach(guards.authGuard)
    : undefined
  const removePermissionGuard = guards.permissionGuard
    ? router.beforeEach(guards.permissionGuard)
    : undefined

  return () => {
    removePermissionGuard?.()
    removeAuthGuard?.()
  }
}
