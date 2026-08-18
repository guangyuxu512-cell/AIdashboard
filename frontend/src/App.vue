<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NLoadingBarProvider,
  NMessageProvider,
  NNotificationProvider,
} from 'naive-ui'
import { RouterView } from 'vue-router'

import { createNaiveThemeOverrides } from '@/app/providers/naive-theme'
import AppShell from '@/shared/components/AppShell.vue'
import type { AppNavigationItem } from '@/shared/components/AppShell.vue'
import StatusTag from '@/shared/components/StatusTag.vue'

const navigation: AppNavigationItem[] = [
  { key: 'foundation', label: 'UI 基础设施', to: '/' },
  { key: 'shops', label: '店铺中心', to: '/shops' },
  { key: 'devices', label: '设备中心', to: '/devices' },
]

const naiveThemeOverrides = createNaiveThemeOverrides()
</script>

<template>
  <NConfigProvider :theme-overrides="naiveThemeOverrides">
    <NGlobalStyle />
    <NLoadingBarProvider>
      <NDialogProvider>
        <NNotificationProvider>
          <NMessageProvider>
            <AppShell :navigation="navigation">
              <template #topbar-actions>
                <StatusTag label="工程模式" tone="info" />
              </template>
              <RouterView />
            </AppShell>
          </NMessageProvider>
        </NNotificationProvider>
      </NDialogProvider>
    </NLoadingBarProvider>
  </NConfigProvider>
</template>
