import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'

import { getModuleDefinition } from '@/app/modules/registry'
import { resolveSafeRedirect } from '@/features/human-auth/model/navigation'
import { useAuthStore } from '@/stores/auth'

export function installAuthGuard(router: Router, pinia: Pinia): void {
  router.beforeEach(async (target) => {
    const auth = useAuthStore(pinia)
    await auth.initialize()

    if (target.meta.public) {
      if (
        target.name === 'login' &&
        auth.isAuthenticated &&
        !auth.requiresTeamSelection
      ) {
        return resolveSafeRedirect(target.query.redirect)
      }
      return true
    }

    if (!auth.isAuthenticated) {
      return {
        name: 'login',
        query: { redirect: target.fullPath },
      }
    }
    if (auth.requiresTeamSelection) {
      return {
        name: 'login',
        query: { redirect: target.fullPath, select_team: '1' },
      }
    }
    if (
      target.meta.requiresAccessAdministrator &&
      !auth.isAccessAdministrator
    ) {
      return { name: 'permission-denied' }
    }
    const moduleCode = target.meta.moduleCode
    const module =
      typeof moduleCode === 'string'
        ? getModuleDefinition(moduleCode)
        : undefined
    if (
      module?.navigationGroup !== 'development' &&
      module &&
      !auth.allowedModuleCodes.has(module.moduleCode)
    ) {
      return { name: 'permission-denied' }
    }
    return true
  })
}
