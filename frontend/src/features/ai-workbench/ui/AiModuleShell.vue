<script setup lang="ts">
import { NAlert } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import AiModuleNavigation from './AiModuleNavigation.vue'

const auth = useAuthStore()
</script>

<template>
  <div class="page-container ai-module-shell">
    <AiModuleNavigation />
    <NAlert
      v-if="auth.isSuperAccount && !auth.hasTeamContext"
      type="info"
      :show-icon="false"
    >
      全部团队仅供浏览，请从右上角选择团队后上传、编辑或生成。
    </NAlert>
    <div class="ai-module-shell__content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ai-module-shell {
  height: 100%;
  min-height: 0;
}

.ai-module-shell__content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}
</style>
