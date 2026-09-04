<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const items = computed(() => [
  ...(auth.isAccessAdministrator
    ? [{ key: 'users', label: '用户与权限' }]
    : []),
  ...(auth.allowedModuleCodes.has('settings')
    ? [{ key: 'notifications', label: '通知配置' }]
    : []),
])

const activeKey = computed(() =>
  route.name === 'access-management' ? 'users' : 'notifications',
)

function select(key: string): void {
  void router.push({
    name: key === 'users' ? 'access-management' : 'notification-settings',
  })
}
</script>

<template>
  <ContextSwitchBar
    v-if="items.length > 1"
    :items="items"
    :active-key="activeKey"
    label="系统设置"
    @select="select"
  />
</template>
