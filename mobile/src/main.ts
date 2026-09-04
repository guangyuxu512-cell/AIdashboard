import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { configureMobileDataSources } from './app/providers/mobile-data-sources'
import { createMobileQueryClient } from './app/providers/query-client'
import router from './app/router'
import {
  createMobileAuthGuard,
  createMobilePermissionGuard,
  installRouteAccessGuards,
} from './app/router/access'
import { MOBILE_ROUTE_NAMES } from './app/router/routes'
import { configureAuthEffects, useAuthStore } from './app/stores/auth'
import { useThemeStore } from './app/stores/theme'
import { configureHumanRequestContext } from './shared/api'
import './app/styles/index.css'

async function bootstrap(): Promise<void> {
  if (import.meta.env.DEV && import.meta.env.VITE_VISUAL_TUNER !== 'false') {
    const { initializeVisualAppearanceTuner, initializeVisualTokenTuner } =
      await import('@/dev/visual-token-tuner')
    initializeVisualTokenTuner()
    initializeVisualAppearanceTuner()
  }

  await configureMobileDataSources()

  const app = createApp(App)
  const pinia = createPinia()
  const queryClient = createMobileQueryClient()

  app.use(pinia)
  const authStore = useAuthStore(pinia)
  configureAuthEffects({
    onTeamChanged: () => queryClient.clear(),
    onAuthCleared: () => queryClient.clear(),
  })
  configureHumanRequestContext({
    getActiveTeamId: () => authStore.activeTeamId,
    onSessionInvalid: () => {
      const currentRoute = router.currentRoute.value
      const redirect = currentRoute.meta.requiresAuth
        ? currentRoute.fullPath
        : undefined
      authStore.expireSession()
      if (currentRoute.name !== MOBILE_ROUTE_NAMES.login) {
        void router.replace({
          name: MOBILE_ROUTE_NAMES.login,
          query: redirect ? { redirect } : undefined,
        })
      }
    },
  })
  installRouteAccessGuards(router, {
    authGuard: createMobileAuthGuard(pinia),
    permissionGuard: createMobilePermissionGuard(pinia),
  })
  app.use(router)
  app.use(VueQueryPlugin, { queryClient })

  useThemeStore(pinia).initialize()
  app.mount('#app')
}

void bootstrap()
