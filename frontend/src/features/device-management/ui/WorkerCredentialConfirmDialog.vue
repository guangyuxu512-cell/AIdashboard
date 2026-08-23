<script setup lang="ts">
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  action: 'rotate' | 'revoke' | null
  deviceName?: string | null
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
    :title="action === 'rotate' ? '确认轮换 Worker Token' : '确认撤销 Worker 凭证'"
    size="sm"
    :positive-text="action === 'rotate' ? '确认轮换' : '确认撤销'"
    negative-text="取消"
    :loading="submitting"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <p v-if="action === 'rotate'">
      轮换后，设备 <strong>{{ deviceName }}</strong> 的旧 Token 将立即失效；需要把新 Token 更新到对应 Worker 电脑。
    </p>
    <p v-else>
      撤销后，设备 <strong>{{ deviceName }}</strong> 的 Worker 将无法继续心跳、领取任务或同步能力，但设备记录不会被删除。
    </p>
  </AppDialog>
</template>

<style scoped>
p {
  margin: 0;
  color: var(--text-secondary);
  line-height: var(--line-height-body);
}

strong {
  color: var(--text-primary);
}
</style>
