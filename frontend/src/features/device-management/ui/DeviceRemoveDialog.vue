<script setup lang="ts">
import type { DeviceListItemViewModel } from '@/entities/device'
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  device: DeviceListItemViewModel | null
  submitting?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  confirm: []
}>()
</script>

<template>
  <AppDialog
    :show="show"
    title="确认移除设备"
    size="sm"
    positive-text="确认移除"
    negative-text="取消"
    :loading="submitting"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <div class="device-remove-dialog">
      <p>移除设备：<strong>{{ device?.deviceName }}</strong></p>
      <p>移除后：</p>
      <ul>
        <li>设备将退出正常设备列表</li>
        <li>Worker Token 立即失效</li>
        <li>店铺绑定将停用</li>
        <li>历史任务和能力记录仍保留</li>
        <li>设备 UUID 不会复用</li>
      </ul>
    </div>
  </AppDialog>
</template>

<style scoped>
.device-remove-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  color: var(--text-secondary);
  line-height: var(--line-height-body);
}

.device-remove-dialog strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

.device-remove-dialog ul {
  margin: 0;
  padding-left: var(--space-5);
}
</style>
