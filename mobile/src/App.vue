<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ConfigProvider as VanConfigProvider, NavBar as VanNavBar } from 'vant'
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import { useThemeStore } from '@/app/stores/theme'
import { MobileAppShell } from '@/shared/ui'

const route = useRoute()
const themeStore = useThemeStore()
const { resolvedTheme } = storeToRefs(themeStore)
const routeTitle = computed(() => route.meta.title || '移动端')
</script>

<template>
  <VanConfigProvider :theme="resolvedTheme">
    <MobileAppShell>
      <template #header>
        <VanNavBar :title="routeTitle" />
      </template>

      <RouterView />
    </MobileAppShell>
  </VanConfigProvider>
</template>
