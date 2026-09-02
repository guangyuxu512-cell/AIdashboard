import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'

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
    return true
  })
}
