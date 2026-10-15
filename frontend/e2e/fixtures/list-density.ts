import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@/shared/styles/theme.css'
import ListDensityHarness from './ListDensityHarness.vue'

createApp(ListDensityHarness).use(createPinia()).mount('#app')
