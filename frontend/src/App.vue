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
import { RouterView } from 'vue-router'

import { createNaiveThemeOverrides } from '@/app/providers/naive-theme'
import AppShell from '@/shared/components/AppShell.vue'
import type { AppNavigationItem } from '@/shared/components/AppShell.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import ThemeSelector from '@/shared/components/ThemeSelector.vue'
import { useThemeStore } from '@/stores/theme'

const navigation: AppNavigationItem[] = [
  ...(import.meta.env.DEV
    ? [{ key: 'foundation', label: 'UI 基础设施', to: '/' }]
    : []),
  { key: 'shops', label: '店铺中心', to: '/shops' },
  { key: 'devices', label: '设备中心', to: '/devices' },
]

const themeStore = useThemeStore()
const isDevelopment = import.meta.env.DEV
const naiveTheme = computed(() =>
  themeStore.resolvedTheme === 'dark' ? darkTheme : null,
)
const naiveThemeOverrides = computed(() =>
  createNaiveThemeOverrides(themeStore.resolvedTheme),
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
      <NDialogProvider>
        <NNotificationProvider>
          <NMessageProvider>
            <AppShell :navigation="navigation">
              <template #topbar-actions>
                <StatusTag v-if="isDevelopment" label="开发" />
                <ThemeSelector />
              </template>
              <RouterView />
            </AppShell>
          </NMessageProvider>
        </NNotificationProvider>
      </NDialogProvider>
    </NLoadingBarProvider>
  </NConfigProvider>
</template>
