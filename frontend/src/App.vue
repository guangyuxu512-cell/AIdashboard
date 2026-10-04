<script setup lang="ts">
import { computed } from 'vue'
import {
  dateZhCN,
  darkTheme,
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NLoadingBarProvider,
  NMessageProvider,
  NNotificationProvider,
  zhCN,
} from 'naive-ui'
import { RouterView, useRoute } from 'vue-router'

import { createNaiveThemeOverrides } from '@/app/providers/naive-theme'
import ClientUpdateNotice from '@/app/ClientUpdateNotice.vue'
import { getNavigationEntries } from '@/app/modules/registry'
import AppShell from '@/shared/components/AppShell.vue'
import CurrentUserMenu from '@/features/human-auth/ui/CurrentUserMenu.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import ThemeSelector from '@/shared/components/ThemeSelector.vue'
import { APP_OVERLAY_HOST_SELECTOR } from '@/shared/ui/overlay-host'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const showDevelopmentModules =
  import.meta.env.DEV &&
  import.meta.env.VITE_SHOW_DEVELOPMENT_MODULES === 'true'
const themeStore = useThemeStore()
const authStore = useAuthStore()
const navigation = computed(() =>
  getNavigationEntries(undefined, {
    includeDevelopment: showDevelopmentModules,
    allowedModuleCodes: authStore.allowedModuleCodes,
  }),
)
const route = useRoute()
const isDevelopment = import.meta.env.DEV
const isAuthLayout = computed(() => route.meta.layout === 'auth')
const naiveTheme = computed(() =>
  themeStore.resolvedTheme === 'dark' ? darkTheme : null,
)
const naiveThemeOverrides = computed(() =>
  createNaiveThemeOverrides(themeStore.resolvedPreset),
)
</script>

<template>
  <NConfigProvider
    abstract
    :theme="naiveTheme"
    :theme-overrides="naiveThemeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NGlobalStyle />
    <NLoadingBarProvider>
      <NDialogProvider :to="APP_OVERLAY_HOST_SELECTOR">
        <NNotificationProvider>
          <NMessageProvider>
            <ClientUpdateNotice />
            <div v-if="isAuthLayout" class="auth-layout">
              <RouterView />
            </div>
            <AppShell v-else :navigation="navigation">
              <template #topbar-actions>
                <StatusTag v-if="isDevelopment" label="开发" />
                <ThemeSelector />
                <CurrentUserMenu />
              </template>
              <RouterView />
            </AppShell>
          </NMessageProvider>
        </NNotificationProvider>
      </NDialogProvider>
    </NLoadingBarProvider>
  </NConfigProvider>
</template>

<style scoped>
.auth-layout {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
