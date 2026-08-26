<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  ConfigProvider as VanConfigProvider,
  NavBar as VanNavBar,
  Tabbar as VanTabbar,
  TabbarItem as VanTabbarItem,
} from 'vant'
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useThemeStore } from '@/app/stores/theme'
import { MobileAppShell } from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const { resolvedTheme } = storeToRefs(themeStore)
const routeTitle = computed(() => route.meta.title || '移动端')
const detailBackTarget = computed<RouteLocationRaw | null>(() => {
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
  return null
})
const showProductNavigation = computed(
  () =>
    route.name === MOBILE_ROUTE_NAMES.home ||
    route.name === MOBILE_ROUTE_NAMES.tasks ||
    route.name === MOBILE_ROUTE_NAMES.devices,
)

function goBack(): void {
  if (detailBackTarget.value) {
    void router.push(detailBackTarget.value)
  }
}
</script>

<template>
  <VanConfigProvider :theme="resolvedTheme">
    <MobileAppShell>
      <template #header>
        <VanNavBar
          :title="routeTitle"
          :left-arrow="detailBackTarget !== null"
          @click-left="goBack"
        />
      </template>

      <RouterView />

      <template v-if="showProductNavigation" #bottom>
        <VanTabbar route :fixed="false" :safe-area-inset-bottom="false">
          <VanTabbarItem
            :to="{ name: MOBILE_ROUTE_NAMES.tasks }"
            icon="todo-list-o"
          >
            任务
          </VanTabbarItem>
          <VanTabbarItem
            :to="{ name: MOBILE_ROUTE_NAMES.devices }"
            icon="desktop-o"
          >
            设备
          </VanTabbarItem>
        </VanTabbar>
      </template>
    </MobileAppShell>
  </VanConfigProvider>
</template>
