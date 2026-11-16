<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ConfigProvider as VanConfigProvider, showToast } from 'vant'
import { computed, defineAsyncComponent, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useAuthStore } from '@/app/stores/auth'
import { useThemeStore, type ThemeMode } from '@/app/stores/theme'
import type { MobileIconName } from '@/shared/icons'
import {
  MobileAppShell,
  MobileBottomNavigation,
  MobileDetailHeader,
  MobileGlobalHeader,
  MobileThemeSettingsSheet,
  provideMobileDetailHeaderAction,
  provideMobileMainHeaderAction,
} from '@/shared/ui'

const visualTokenTunerEnabled =
  import.meta.env.DEV && import.meta.env.VITE_VISUAL_TUNER !== 'false'
const VisualTokenTuner = visualTokenTunerEnabled
  ? defineAsyncComponent(
      () => import('@/dev/visual-token-tuner/VisualTokenTuner.vue'),
    )
  : null

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const { mode, resolvedTheme } = storeToRefs(themeStore)
const themeSettingsOpen = ref(false)
const detailHeader = provideMobileDetailHeaderAction()
const mainHeader = provideMobileMainHeaderAction()

const routeTitle = computed(() => route.meta.title || '移动端')
const shellLayout = computed(() => route.meta.layout || 'main')
const isMainLayout = computed(() => shellLayout.value === 'main')
const isAuthLayout = computed(() => shellLayout.value === 'auth')
const isToolLayout = computed(() => shellLayout.value === 'tool')
const globalHeaderPageTitle = computed(() =>
  route.name === MOBILE_ROUTE_NAMES.devices
    ? '设备'
    : route.name === MOBILE_ROUTE_NAMES.tasks
      ? '任务'
      : undefined,
)
const isVisualV2Route = computed(
  () =>
    route.name === MOBILE_ROUTE_NAMES.devices ||
    route.name === MOBILE_ROUTE_NAMES.deviceDetail ||
    route.name === MOBILE_ROUTE_NAMES.tasks ||
    route.name === MOBILE_ROUTE_NAMES.taskDetail,
)
const detailHeaderAction = computed(() => detailHeader.action.value)
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
const showBottomNavigation = computed(
  () =>
    Boolean(activeNavigationKey.value) ||
    route.name === MOBILE_ROUTE_NAMES.home ||
    route.name === MOBILE_ROUTE_NAMES.foundation,
)

const allMainNavigationItems = [
  {
    key: 'devices',
    label: '设备',
    icon: 'device-nav' satisfies MobileIconName,
    to: { name: MOBILE_ROUTE_NAMES.devices },
    permission: 'device',
  },
  {
    key: 'tasks',
    label: '任务',
    icon: 'task-nav' satisfies MobileIconName,
    to: { name: MOBILE_ROUTE_NAMES.tasks },
    permission: 'task',
  },
  {
    key: 'schedules',
    label: '计划',
    icon: 'schedule-nav' satisfies MobileIconName,
    to: { name: MOBILE_ROUTE_NAMES.schedules },
    permission: 'schedule',
  },
  {
    key: 'shops',
    label: '店铺',
    icon: 'shop-nav' satisfies MobileIconName,
    to: { name: MOBILE_ROUTE_NAMES.shops },
    permission: 'shop',
  },
  {
    key: 'profile',
    label: '我的',
    icon: 'profile-nav' satisfies MobileIconName,
    to: { name: MOBILE_ROUTE_NAMES.profile },
    permission: null,
  },
] as const

const mainNavigationItems = computed(() => {
  if (route.name === MOBILE_ROUTE_NAMES.foundation) {
    return allMainNavigationItems
  }
  return allMainNavigationItems.filter(
    (item) =>
      item.permission === null ||
      authStore.allowedModuleCodes.has(item.permission),
  )
})

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

function runDetailHeaderAction(): void {
  detailHeaderAction.value?.run()
}

function selectTheme(nextMode: ThemeMode): void {
  themeStore.setMode(nextMode)
  themeSettingsOpen.value = false
}

function runMainHeaderAction(): void {
  if (mainHeader.action.value) {
    mainHeader.action.value.run()
    return
  }
  themeSettingsOpen.value = true
}
</script>

<template>
  <VanConfigProvider :theme="resolvedTheme">
    <RouterView v-if="isToolLayout || isAuthLayout" />

    <MobileAppShell
      v-else
      :class="{
        'mobile-app-shell--visual-v2': isVisualV2Route,
      }"
    >
      <template #header>
        <MobileGlobalHeader
          v-if="isMainLayout"
          :resolved-theme="resolvedTheme"
          :page-title="globalHeaderPageTitle"
          :menu-enabled="Boolean(globalHeaderPageTitle)"
          :menu-action-label="mainHeader.action.value?.label ?? '打开主题设置'"
          @theme-toggle="themeStore.toggleResolvedTheme"
          @notification-click="showNotificationPlaceholder"
          @settings-click="runMainHeaderAction"
        />
        <MobileDetailHeader
          v-else
          :title="routeTitle"
          :visual-v2="isVisualV2Route"
          :right-action="detailHeaderAction"
          @back="goBack"
          @right="runDetailHeaderAction"
        />
      </template>

      <RouterView />

      <template #bottom>
        <MobileBottomNavigation
          v-if="showBottomNavigation"
          :items="mainNavigationItems"
          :active-key="activeNavigationKey"
        />
      </template>
    </MobileAppShell>

    <component
      :is="VisualTokenTuner"
      v-if="visualTokenTunerEnabled && !isToolLayout && !isAuthLayout"
    />

    <MobileThemeSettingsSheet
      v-if="!isToolLayout && !isAuthLayout"
      :show="themeSettingsOpen"
      :mode="mode"
      @update:show="themeSettingsOpen = $event"
      @select="selectTheme"
    />
  </VanConfigProvider>
</template>
