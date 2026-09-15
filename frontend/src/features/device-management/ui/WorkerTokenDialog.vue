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
const copying = ref(false)
let copyFailureNotified = false
const clipboardErrorTypes = new Set([
  'AbortError',
  'NotAllowedError',
  'NotFoundError',
  'NotReadableError',
  'SecurityError',
  'TypeError',
  'UnknownError',
])

watch(
  () => props.show,
  (show) => {
    if (show) {
      revealed.value = false
      copyFailureNotified = false
    }
  },
)

async function copyToken(): Promise<void> {
  if (!props.token || copying.value) return
  copying.value = true
  try {
    const clipboard = navigator.clipboard
    if (!clipboard || typeof clipboard.writeText !== 'function') {
      throw new TypeError('ClipboardWriteUnavailable')
    }
    await clipboard.writeText(props.token)
    copyFailureNotified = false
    message.success('Worker Token 已复制')
  } catch (error) {
    if (!copyFailureNotified) {
      console.warn(
        '[worker-token-copy] clipboard write failed',
        getClipboardErrorType(error),
      )
      message.error('Worker Token 复制失败，请点击“显示”后手动选中复制')
      copyFailureNotified = true
    }
  } finally {
    copying.value = false
  }
}

function getClipboardErrorType(error: unknown): string {
  if (
    error &&
    typeof error === 'object' &&
    'name' in error &&
    typeof error.name === 'string' &&
    clipboardErrorTypes.has(error.name)
  ) {
    return error.name
  }
  return error && typeof error === 'object' ? 'Error' : typeof error
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
        :disabled="!revealed || !token"
        :readonly="revealed"
        aria-label="Worker Token"
      />
      <div class="worker-token-dialog__actions">
        <AppButton tone="text" @click="revealed = !revealed">
          {{ revealed ? '隐藏' : '显示' }}
        </AppButton>
        <AppButton
          tone="primary"
          :loading="copying"
          :disabled="!token || copying"
          @click="copyToken"
        >
          {{ copying ? '复制中' : '复制' }}
        </AppButton>
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
