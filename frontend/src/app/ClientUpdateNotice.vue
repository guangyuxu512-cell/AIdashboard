<script setup lang="ts">
import { h, onBeforeUnmount, ref, watch } from 'vue'
import { useNotification } from 'naive-ui'
import type { NotificationReactive } from 'naive-ui'

import AppButton from '@/shared/ui/AppButton.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'
import { clientUpdateRequired } from './client-update'

const notifications = useNotification()
const confirmReload = ref(false)
let notice: NotificationReactive | undefined

watch(
  clientUpdateRequired,
  (required) => {
    if (!required || notice) return
    notice = notifications.warning({
      title: '页面资源暂不可用',
      content:
        '可能已发布新版本或网络连接中断。当前内容已保留，请先保存正在编辑的内容。',
      duration: 0,
      closable: false,
      action: () =>
        h(
          AppButton,
          {
            onClick: () => {
              confirmReload.value = true
            },
          },
          () => '重新加载',
        ),
    })
  },
  { immediate: true },
)

function reload(): void {
  // Only explicit confirmation may discard in-memory forms. Do not auto-save
  // arbitrary forms or persist credentials as part of recovery.
  window.location.reload()
}

onBeforeUnmount(() => notice?.destroy())
</script>

<template>
  <AppDialog
    v-model:show="confirmReload"
    title="重新加载页面？"
    positive-text="已保存，重新加载"
    negative-text="继续编辑"
    size="sm"
    @confirm="reload"
    @cancel="confirmReload = false"
  >
    重新加载会丢失尚未保存的表单内容。请选择“继续编辑”完成保存；确认无需保留未保存内容后再重新加载。
  </AppDialog>
</template>
