<script setup lang="ts">
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{ show: boolean }>()

defineEmits<{ 'update:show': [value: boolean] }>()
</script>

<template>
  <AppDialog
    :show="show"
    title="添加设备"
    size="sm"
    positive-text="知道了"
    negative-text="关闭"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('update:show', false)"
  >
    <div class="add-device-info">
      <strong>设备需要安装 Worker 后由服务器注册</strong>
      <p>
        当前阶段仅展示设备管理界面，不提供设备注册、连接或系统资源采集能力。
      </p>
    </div>
  </AppDialog>
</template>

<style scoped>
.add-device-info {
  padding: var(--space-2) 0;
}

.add-device-info strong {
  display: block;
  font-weight: var(--font-weight-semibold);
}

.add-device-info p {
  margin-top: var(--space-2);
  color: var(--color-text-secondary);
}
</style>
