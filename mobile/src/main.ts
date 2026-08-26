import { VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { createMobileQueryClient } from './app/providers/query-client'
import router from './app/router'
import { useThemeStore } from './app/stores/theme'
import './app/styles/index.css'

const app = createApp(App)
const pinia = createPinia()
const queryClient = createMobileQueryClient()

app.use(pinia)
app.use(router)
app.use(VueQueryPlugin, { queryClient })

useThemeStore(pinia).initialize()

app.mount('#app')
