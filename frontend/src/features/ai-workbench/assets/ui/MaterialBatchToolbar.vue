<script setup lang="ts">
import { Download, Trash2 } from '@lucide/vue'

import TableToolbar from '@/shared/components/TableToolbar.vue'
import { AppButton, AppCheckbox } from '@/shared/ui'

defineProps<{
  selectionMode: boolean
  selectedCount: number
  currentPageCount: number
  checked: boolean
  indeterminate: boolean
  readOnly?: boolean
}>()

defineEmits<{
  'start-selection': []
  'toggle-all': [value: boolean]
  download: []
  remove: []
  finish: []
}>()
</script>

<template>
  <TableToolbar class="material-batch-toolbar" aria-label="素材批量操作">
    <AppButton
      v-if="!selectionMode"
      :disabled="currentPageCount === 0"
      aria-label="选择"
      @click="$emit('start-selection')"
    >
      选择
    </AppButton>
    <span v-else class="material-batch-toolbar__selection">
      已选 <strong>{{ selectedCount }}</strong>
    </span>
    <AppCheckbox
      :model-value="checked"
      :indeterminate="indeterminate"
      :disabled="currentPageCount === 0"
      aria-label="全选"
      @update:model-value="$emit('toggle-all', $event)"
    >
      全选
    </AppCheckbox>
    <template #actions>
      <template v-if="selectionMode">
        <AppButton
          :disabled="selectedCount === 0"
          aria-label="批量下载"
          @click="$emit('download')"
        >
          <Download :size="16" />
          下载
        </AppButton>
        <AppButton
          tone="danger"
          :disabled="readOnly || selectedCount === 0"
          aria-label="批量删除"
          @click="$emit('remove')"
        >
          <Trash2 :size="16" />
          删除
        </AppButton>
        <AppButton tone="text" aria-label="完成" @click="$emit('finish')">
          完成
        </AppButton>
      </template>
    </template>
  </TableToolbar>
</template>

<style scoped>
.material-batch-toolbar {
  flex: 0 0 auto;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}

.material-batch-toolbar__selection {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.material-batch-toolbar__selection strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}
</style>
