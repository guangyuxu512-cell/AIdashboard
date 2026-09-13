import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp, watch } from 'vue'

import App from './App.vue'
import router from './app/router'
import { installClientUpdateDetection } from './app/client-update'
import { installAuthGuard } from './app/router/auth-guard'
import {
  queryClient,
  resetQueriesForActorContextChange,
} from './app/providers/query-client'
import { useAiWorkbenchSessionStore } from './features/ai-workbench/generation/model/useAiWorkbenchSessionStore'
import { configureHumanRequestContext } from './shared/api'
import { configureAuthEffects, useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import './shared/styles/theme.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
const authStore = useAuthStore(pinia)
const aiWorkbenchSessionStore = useAiWorkbenchSessionStore(pinia)
configureAuthEffects({
  onTeamChanged: () => {
    aiWorkbenchSessionStore.clearActiveActorContext()
    void resetQueriesForActorContextChange()
  },
  onAuthCleared: () => {
    aiWorkbenchSessionStore.clearActiveActorContext()
    queryClient.clear()
  },
  onAuthRestoreRejected: () => {
    aiWorkbenchSessionStore.clearLastPersistedActorContext()
  },
})
watch(
  [
    () => authStore.status,
    () => authStore.currentUser?.userId ?? null,
    () => authStore.activeTeamId,
    () => authStore.currentModuleAccess,
  ],
  ([status, userId, teamId, moduleAccess]) => {
    if (
      status === 'authenticated' &&
      userId &&
      teamId &&
      moduleAccess?.moduleCodes.includes('ai-workbench')
    ) {
      if (!aiWorkbenchSessionStore.hasActiveActorContext) {
        aiWorkbenchSessionStore.activateActorContext({ userId, teamId })
      }
      void aiWorkbenchSessionStore.resumePendingSubmissions()
    }
  },
  { immediate: true, flush: 'post' },
)
configureHumanRequestContext({
  getActiveTeamId: () => authStore.activeTeamId,
  onSessionInvalid: () => {
    const redirect = router.currentRoute.value.fullPath
    authStore.expireSession()
    if (router.currentRoute.value.name !== 'login') {
      void router.replace({ name: 'login', query: { redirect } })
    }
  },
})
installAuthGuard(router, pinia)
installClientUpdateDetection(router)
app.use(router)
app.use(VueQueryPlugin, { queryClient })
useThemeStore(pinia).initialize()
app.mount('#app')
