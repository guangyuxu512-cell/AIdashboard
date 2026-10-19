<script setup lang="ts">
import { computed } from 'vue'
import { ChevronDown } from '@lucide/vue'
import { NDropdown, useMessage } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'
import { useRouter } from 'vue-router'

import { getErrorMessage } from '@/shared/api'
import AppButton from '@/shared/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()

const options = computed<DropdownOption[]>(() => {
  const items: DropdownOption[] = [
    {
      key: 'current-user',
      label: `当前用户：${auth.currentUser?.displayName ?? '—'}`,
      disabled: true,
    },
    {
      key: 'account-type',
      label: `账号类型：${auth.isSuperAccount ? '超级管理员' : '普通成员'}`,
      disabled: true,
    },
    {
      key: 'current-team',
      label: auth.isSuperAccount
        ? auth.currentTeam
          ? `当前团队：${auth.currentTeam.teamName}`
          : '当前范围：全部团队'
        : `当前团队：${auth.currentTeam?.teamName ?? '未分配团队'}`,
      disabled: true,
    },
  ]
  if (auth.isSuperAccount || auth.activeTeams.length > 1) {
    items.push({ type: 'divider', key: 'team-divider' })
    if (auth.isSuperAccount) {
      items.push({
        key: 'all-teams',
        label: auth.activeTeamId === null ? '✓ 全部团队' : '切换至全部团队',
      })
    }
    items.push(
      ...auth.activeTeams.map((team) => ({
        key: `team:${team.teamId}`,
        label:
          team.teamId === auth.activeTeamId
            ? `✓ ${team.teamName}`
            : `切换至 ${team.teamName}`,
      })),
    )
  }
  items.push({ type: 'divider', key: 'logout-divider' })
  items.push({ key: 'logout', label: '退出登录' })
  return items
})

async function select(key: string | number): Promise<void> {
  if (typeof key !== 'string') return
  if (key === 'all-teams' || key.startsWith('team:')) {
    try {
      await auth.selectTeam(
        key === 'all-teams' ? null : key.slice('team:'.length),
      )
    } catch (error) {
      message.error(getErrorMessage(error))
    }
    return
  }
  if (key !== 'logout') return
  try {
    await auth.logout()
    await router.replace({ name: 'login' })
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <NDropdown trigger="click" :options="options" @select="select">
    <AppButton tone="text" class="current-user-menu" aria-label="当前用户菜单">
      <span class="current-user-menu__name">
        {{ auth.currentUser?.displayName ?? '当前用户' }}
      </span>
      <ChevronDown :size="14" :stroke-width="1.8" aria-hidden="true" />
    </AppButton>
  </NDropdown>
</template>

<style scoped>
.current-user-menu__name {
  max-width: var(--field-width-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
