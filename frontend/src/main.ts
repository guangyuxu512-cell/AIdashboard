import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './app/router'
import { installClientUpdateDetection } from './app/client-update'
import { installAuthGuard } from './app/router/auth-guard'
import {
  queryClient,
  resetQueriesForActorContextChange,
} from './app/providers/query-client'
import { configureHumanRequestContext } from './shared/api'
import { cancelAllAutoSearches } from './shared/composables/useAutoSearch'
import { configureAuthEffects, useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import './shared/styles/theme.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
const authStore = useAuthStore(pinia)
configureAuthEffects({
  onTeamChanged: () => {
    cancelAllAutoSearches()
    void resetQueriesForActorContextChange()
  },
  onAuthCleared: () => {
    queryClient.clear()
  },
})
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
