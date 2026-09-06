import type { Pinia } from 'pinia'
import type { NavigationGuard, Router } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useAuthStore } from '@/app/stores/auth'
import { isLoginRouteName, resolvePostAuthRoute } from '@/features/human-auth'

export interface RouteAccessGuards {
  authGuard?: NavigationGuard
  permissionGuard?: NavigationGuard
}

export function createMobileAuthGuard(pinia: Pinia): NavigationGuard {
  return async (target) => {
    const auth = useAuthStore(pinia)

    if (target.meta.requiresAuth || isLoginRouteName(target.name)) {
      await auth.initialize()
    }

    if (isLoginRouteName(target.name)) {
      if (auth.isAuthenticated && !auth.requiresTeamSelection) {
        return resolvePostAuthRoute(
          target.query.redirect,
          auth.allowedModuleCodes,
        )
      }
      return true
    }

    if (!target.meta.requiresAuth) return true
    if (!auth.isAuthenticated || auth.requiresTeamSelection) {
      return {
        name: MOBILE_ROUTE_NAMES.login,
        query: { redirect: target.fullPath },
      }
    }
    return true
  }
}

export function createMobilePermissionGuard(pinia: Pinia): NavigationGuard {
  return (target) => {
    const permission = target.meta.permission
    if (permission && !useAuthStore(pinia).allowedModuleCodes.has(permission)) {
      return { name: MOBILE_ROUTE_NAMES.permissionDenied }
    }
    return true
  }
}

/**
 * Installs the formal Human Session and Module Access guards.
 *
 * Registration order is intentionally fixed: authentication first, permission
 * second. Neither guard creates fallback identities, tokens, roles or module
 * grants.
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
