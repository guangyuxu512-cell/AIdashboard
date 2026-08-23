<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { ref, watch } from 'vue'

import AppButton from '@/shared/ui/AppButton.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'

const props = defineProps<{
  show: boolean
  token: string | null
}>()

defineEmits<{
  'update:show': [value: boolean]
}>()

const message = useMessage()
const revealed = ref(false)

watch(
  () => props.show,
  (show) => {
    if (show) revealed.value = false
  },
)

async function copyToken(): Promise<void> {
  if (!props.token) return
  try {
    await navigator.clipboard.writeText(props.token)
    message.success('Worker Token 已复制')
  } catch {
    message.error('Worker Token 复制失败')
  }
}
</script>

<template>
  <AppDialog
    :show="show"
    title="Worker Token"
    size="md"
    positive-text="关闭"
    :show-negative="false"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('update:show', false)"
  >
    <template #description>
      该 Token 仅本次显示。关闭后无法再次查看，请立即复制到对应 Worker 电脑。
    </template>
    <div class="worker-token-dialog">
      <AppInput
        :model-value="token"
        :type="revealed ? 'text' : 'password'"
        disabled
      />
      <div class="worker-token-dialog__actions">
        <AppButton tone="text" @click="revealed = !revealed">
          {{ revealed ? '隐藏' : '显示' }}
        </AppButton>
        <AppButton tone="primary" @click="copyToken">复制</AppButton>
      </div>
    </div>
  </AppDialog>
</template>

<style scoped>
.worker-token-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.worker-token-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
