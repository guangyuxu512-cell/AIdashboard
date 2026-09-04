<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  showToast,
} from 'vant'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { useAuthStore } from '@/app/stores/auth'
import { AppPage } from '@/shared/ui'

const auth = useAuthStore()
const router = useRouter()

async function logout(): Promise<void> {
  try {
    await auth.logout()
    await router.replace({ name: MOBILE_ROUTE_NAMES.login })
  } catch {
    showToast('退出失败，请重试')
  }
}
</script>

<template>
  <AppPage class="profile-page" label="我的">
    <VanCellGroup inset>
      <VanCell title="当前用户" :value="auth.currentUser?.displayName ?? '—'" />
      <VanCell title="当前团队" :value="auth.currentTeam?.teamName ?? '—'" />
    </VanCellGroup>
    <VanButton block type="default" @click="logout">退出登录</VanButton>
  </AppPage>
</template>

<style scoped>
.profile-page :deep(.van-cell-group--inset) {
  margin: 0;
}
</style>
