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
    ? [
        { key: 'users', label: '用户与权限' },
        { key: 'audit-logs', label: '操作日志' },
      ]
    : []),
  ...(auth.allowedModuleCodes.has('settings')
    ? [{ key: 'notifications', label: '通知配置' }]
    : []),
])

const activeKey = computed(() => {
  if (route.name === 'access-management') return 'users'
  if (route.name === 'audit-logs') return 'audit-logs'
  return 'notifications'
})

function select(key: string): void {
  if (key === 'audit-logs') {
    void router.push({ name: 'audit-logs' })
    return
  }
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
