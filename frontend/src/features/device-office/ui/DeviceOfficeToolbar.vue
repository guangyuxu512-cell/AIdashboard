<script setup lang="ts">
import type { DeviceCenterViewMode } from '../model/types'

import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'

defineProps<{
  total: number
  online: number
  offline: number
  search: string
  viewMode: DeviceCenterViewMode
  loading?: boolean
}>()

defineEmits<{
  'update:search': [value: string]
  'update:viewMode': [value: DeviceCenterViewMode]
  refresh: []
  add: []
}>()
</script>

<template>
  <section class="device-office-toolbar" aria-label="设备中心工具栏">
    <div class="device-office-toolbar__counts" aria-label="设备统计">
      <span>设备 <strong>{{ total }}</strong></span>
      <span class="is-online">在线 <strong>{{ online }}</strong></span>
      <span class="is-offline">离线 <strong>{{ offline }}</strong></span>
    </div>

    <div class="device-office-toolbar__actions">
      <AppInput
        :model-value="search"
        width="md"
        clearable
        placeholder="搜索当前页设备"
        aria-label="搜索设备"
        @update:model-value="$emit('update:search', $event)"
      />
      <AppButton :loading="loading" @click="$emit('refresh')">刷新</AppButton>
      <div class="device-office-toolbar__view-switch" aria-label="设备视图">
        <AppButton
          :tone="viewMode === 'office' ? 'primary' : 'secondary'"
          @click="$emit('update:viewMode', 'office')"
        >
          办公区
        </AppButton>
        <AppButton
          :tone="viewMode === 'list' ? 'primary' : 'secondary'"
          @click="$emit('update:viewMode', 'list')"
        >
          列表
        </AppButton>
      </div>
      <AppButton tone="primary" @click="$emit('add')">+ 添加设备</AppButton>
    </div>
  </section>
</template>

<style scoped>
.device-office-toolbar,
.device-office-toolbar__counts,
.device-office-toolbar__actions,
.device-office-toolbar__view-switch {
  display: flex;
  align-items: center;
}

.device-office-toolbar {
  min-width: 0;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(var(--glass-blur));
}

.device-office-toolbar__counts,
.device-office-toolbar__actions {
  gap: var(--space-3);
}

.device-office-toolbar__counts span {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  white-space: nowrap;
}

.device-office-toolbar__counts strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

.device-office-toolbar__counts .is-online strong {
  color: var(--status-success);
}

.device-office-toolbar__counts .is-offline strong {
  color: var(--text-tertiary);
}

.device-office-toolbar__view-switch {
  gap: var(--space-1);
}

@media (max-width: 1180px) {
  .device-office-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .device-office-toolbar__actions {
    flex-wrap: wrap;
  }
}
</style>
