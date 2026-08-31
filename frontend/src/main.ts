import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './app/router'
import { installAuthGuard } from './app/router/auth-guard'
import {
  queryClient,
  resetQueriesForActorContextChange,
} from './app/providers/query-client'
import { configureHumanRequestContext } from './shared/api'
import { configureAuthEffects, useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import './shared/styles/theme.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
const authStore = useAuthStore(pinia)
configureAuthEffects({
  onTeamChanged: () => void resetQueriesForActorContextChange(),
  onAuthCleared: () => queryClient.clear(),
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
app.use(router)
app.use(VueQueryPlugin, { queryClient })
useThemeStore(pinia).initialize()
app.mount('#app')
