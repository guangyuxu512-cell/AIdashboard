<script setup lang="ts">
import { NModal } from 'naive-ui'

import AppButton from './AppButton.vue'
import type { OverlaySize } from './types'

const dialogWidths: Record<OverlaySize, string> = {
  sm: 'var(--dialog-width-sm)',
  md: 'var(--dialog-width-md)',
  lg: 'var(--dialog-width-lg)',
}

withDefaults(
  defineProps<{
    show: boolean
    title: string
    size?: OverlaySize
    positiveText?: string
    negativeText?: string
    loading?: boolean
  }>(),
  {
    size: 'md',
    positiveText: '确认',
    negativeText: '取消',
    loading: false,
  },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: []
  cancel: []
}>()

function cancel(): void {
  emit('update:show', false)
  emit('cancel')
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="title"
    :style="{
      width: dialogWidths[size],
      maxWidth: 'calc(100vw - var(--space-8))',
    }"
    :bordered="true"
    :mask-closable="false"
    @update:show="$emit('update:show', $event)"
  >
    <slot />
    <template #footer>
      <div class="app-dialog__footer">
        <AppButton @click="cancel">{{ negativeText }}</AppButton>
        <AppButton tone="primary" :loading="loading" @click="$emit('confirm')">
          {{ positiveText }}
        </AppButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.app-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
</style>
