<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ConfigProvider as VanConfigProvider, showToast } from 'vant'
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useThemeStore } from '@/app/stores/theme'
import {
  MobileAppShell,
  MobileBottomNavigation,
  MobileDetailHeader,
  MobileGlobalHeader,
} from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const { resolvedTheme } = storeToRefs(themeStore)

const routeTitle = computed(() => route.meta.title || '移动端')
const shellLayout = computed(() => route.meta.layout || 'main')
const isMainLayout = computed(() => shellLayout.value === 'main')
const activeNavigationKey = computed(() => {
  if (
    route.name === MOBILE_ROUTE_NAMES.devices ||
    route.name === MOBILE_ROUTE_NAMES.deviceDetail
  ) {
    return 'devices'
  }
  if (
    route.name === MOBILE_ROUTE_NAMES.tasks ||
    route.name === MOBILE_ROUTE_NAMES.taskDetail
  ) {
    return 'tasks'
  }
  if (route.name === MOBILE_ROUTE_NAMES.schedules) return 'schedules'
  if (route.name === MOBILE_ROUTE_NAMES.shops) return 'shops'
  if (route.name === MOBILE_ROUTE_NAMES.profile) return 'profile'
  return ''
})

const mainNavigationItems = [
  {
    key: 'devices',
    label: '设备',
    icon: 'desktop-o',
    to: { name: MOBILE_ROUTE_NAMES.devices },
  },
  {
    key: 'tasks',
    label: '任务',
    icon: 'todo-list-o',
    to: { name: MOBILE_ROUTE_NAMES.tasks },
  },
  {
    key: 'schedules',
    label: '计划',
    icon: 'calendar-o',
    to: { name: MOBILE_ROUTE_NAMES.schedules },
  },
  {
    key: 'shops',
    label: '店铺',
    icon: 'shop-o',
    to: { name: MOBILE_ROUTE_NAMES.shops },
  },
  {
    key: 'profile',
    label: '我的',
    icon: 'user-o',
    to: { name: MOBILE_ROUTE_NAMES.profile },
  },
] as const

const detailBackTarget = computed<RouteLocationRaw>(() => {
  if (route.name === MOBILE_ROUTE_NAMES.taskDetail) {
    const fromDeviceId = route.query.fromDeviceId
    if (typeof fromDeviceId === 'string' && fromDeviceId.length > 0) {
      return {
        name: MOBILE_ROUTE_NAMES.deviceDetail,
        params: { deviceId: fromDeviceId },
      }
    }
    return { name: MOBILE_ROUTE_NAMES.tasks }
  }
  if (route.name === MOBILE_ROUTE_NAMES.deviceDetail) {
    return { name: MOBILE_ROUTE_NAMES.devices }
  }
  return { name: MOBILE_ROUTE_NAMES.home }
})

function goBack(): void {
  void router.push(detailBackTarget.value)
}

function showNotificationPlaceholder(): void {
  showToast('功能建设中')
}
</script>

<template>
  <VanConfigProvider :theme="resolvedTheme">
    <MobileAppShell>
      <template #header>
        <MobileGlobalHeader
          v-if="isMainLayout"
          :resolved-theme="resolvedTheme"
          @theme-toggle="themeStore.toggleResolvedTheme"
          @notification-click="showNotificationPlaceholder"
        />
        <MobileDetailHeader v-else :title="routeTitle" @back="goBack" />
      </template>

      <RouterView />

      <template #bottom>
        <MobileBottomNavigation
          :items="mainNavigationItems"
          :active-key="activeNavigationKey"
        />
      </template>
    </MobileAppShell>
  </VanConfigProvider>
</template>
