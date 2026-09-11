<script setup lang="ts">
import { AppButton } from '@/shared/ui'

defineProps<{
  isDownloading: boolean
  progressLabel: string
  failedCount: number
}>()

defineEmits<{
  cancel: []
  retryFailed: []
}>()
</script>

<template>
  <div
    v-if="isDownloading || failedCount"
    class="asset-download-status"
    aria-live="polite"
  >
    <span v-if="isDownloading">正在下载 {{ progressLabel }}</span>
    <span v-else>有 {{ failedCount }} 个文件下载失败</span>
    <AppButton v-if="isDownloading" tone="text" @click="$emit('cancel')">
      取消下载
    </AppButton>
    <AppButton v-else tone="text" @click="$emit('retryFailed')">
      重试失败项
    </AppButton>
  </div>
</template>

<style scoped>
.asset-download-status {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  color: var(--app-text-secondary);
  font-size: var(--app-font-size-sm);
}
</style>
