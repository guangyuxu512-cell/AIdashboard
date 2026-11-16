<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  AI_WORKBENCH_NAVIGATION,
  AI_WORKBENCH_ROUTES,
} from '@/features/ai-workbench/model/routes'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'

const route = useRoute()
const router = useRouter()

const activeRouteName = computed(() =>
  typeof route.name === 'string'
    ? route.name
    : AI_WORKBENCH_ROUTES.generate.name,
)

const navigationItems = AI_WORKBENCH_NAVIGATION.map((item) => ({
  key: item.name,
  label: item.label,
}))

function navigate(routeName: string): void {
  const destination = AI_WORKBENCH_NAVIGATION.find(
    (item) => item.name === routeName,
  )

  if (destination && destination.name !== route.name) {
    const query =
      import.meta.env.DEV && route.query.visualMock === '1'
        ? { visualMock: '1' }
        : undefined
    void router.push({ name: destination.name, query })
  }
}
</script>

<template>
  <ContextSwitchBar
    class="ai-module-navigation"
    label="AI 功能入口"
    :items="navigationItems"
    :active-key="activeRouteName"
    @select="navigate"
  />
</template>
