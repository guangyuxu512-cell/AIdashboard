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

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useThemeStore } from '@/app/stores/theme'
import { MobileAppShell } from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const { resolvedTheme } = storeToRefs(themeStore)
const routeTitle = computed(() => route.meta.title || '移动端')
const isTaskDetail = computed(
  () => route.name === MOBILE_ROUTE_NAMES.taskDetail,
)
const showTaskNavigation = computed(
  () =>
    route.name === MOBILE_ROUTE_NAMES.home ||
    route.name === MOBILE_ROUTE_NAMES.tasks,
)

function goBack(): void {
  void router.push({ name: MOBILE_ROUTE_NAMES.tasks })
}
</script>

<template>
  <VanConfigProvider :theme="resolvedTheme">
    <MobileAppShell>
      <template #header>
        <VanNavBar
          :title="routeTitle"
          :left-arrow="isTaskDetail"
          @click-left="goBack"
        />
      </template>

      <RouterView />

      <template v-if="showTaskNavigation" #bottom>
        <VanTabbar route :fixed="false" :safe-area-inset-bottom="false">
          <VanTabbarItem
            :to="{ name: MOBILE_ROUTE_NAMES.tasks }"
            icon="todo-list-o"
          >
            任务
          </VanTabbarItem>
        </VanTabbar>
      </template>
    </MobileAppShell>
  </VanConfigProvider>
</template>
