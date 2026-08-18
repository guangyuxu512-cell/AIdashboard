<script setup lang="ts">
import TableToolbar from '@/shared/components/TableToolbar.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{ selectedCount: number }>()
</script>

<template>
  <TableToolbar class="shop-batch-toolbar" aria-label="店铺批量操作">
    <span class="shop-batch-toolbar__selection">
      已选择 <strong>{{ selectedCount }}</strong> 家店铺
    </span>
    <span class="shop-batch-toolbar__placeholder">批量能力待接入</span>

    <template #actions>
      <AppButton disabled title="自动化总开关尚未接入">批量开启</AppButton>
      <AppButton disabled title="自动化总开关尚未接入">批量关闭</AppButton>
      <AppButton tone="danger" disabled title="店铺删除 API 尚未接入">
        批量删除
      </AppButton>
    </template>
  </TableToolbar>
</template>

<style scoped>
.shop-batch-toolbar {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.shop-batch-toolbar__selection {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.shop-batch-toolbar__selection strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

.shop-batch-toolbar__placeholder {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
