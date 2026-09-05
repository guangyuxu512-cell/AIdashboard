<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/shared/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

interface SettingsNavigationItem {
  key: 'users' | 'audit-logs' | 'notifications'
  label: string
  routeName: 'access-management' | 'audit-logs' | 'notification-settings'
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const items = computed<SettingsNavigationItem[]>(() => [
  ...(auth.isAccessAdministrator
    ? [
        {
          key: 'users' as const,
          label: '用户与权限',
          routeName: 'access-management' as const,
        },
        {
          key: 'audit-logs' as const,
          label: '操作日志',
          routeName: 'audit-logs' as const,
        },
      ]
    : []),
  ...(auth.allowedModuleCodes.has('settings')
    ? [
        {
          key: 'notifications' as const,
          label: '通知配置',
          routeName: 'notification-settings' as const,
        },
      ]
    : []),
])

function isActive(item: SettingsNavigationItem): boolean {
  return route.name === item.routeName
}

function select(item: SettingsNavigationItem): void {
  if (!isActive(item)) void router.push({ name: item.routeName })
}
</script>

<template>
  <nav class="settings-side-nav" aria-label="系统设置">
    <AppButton
      v-for="item in items"
      :key="item.key"
      class="settings-side-nav__item"
      :class="{ 'settings-side-nav__item--active': isActive(item) }"
      :tone="isActive(item) ? 'secondary' : 'text'"
      block
      :aria-current="isActive(item) ? 'page' : undefined"
      @click="select(item)"
    >
      {{ item.label }}
    </AppButton>
  </nav>
</template>

<style scoped>
.settings-side-nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.settings-side-nav__item :deep(.n-button__content) {
  width: 100%;
  justify-content: flex-start;
}

.settings-side-nav__item--active {
  color: var(--accent-primary);
}

@media (max-width: 900px) {
  .settings-side-nav {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .settings-side-nav__item {
    width: auto;
  }
}
</style>
