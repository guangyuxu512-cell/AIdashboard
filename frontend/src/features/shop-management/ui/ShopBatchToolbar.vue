<script setup lang="ts">
import TableToolbar from '@/shared/components/TableToolbar.vue'

defineProps<{ selectedCount: number }>()
</script>

<template>
  <TableToolbar class="shop-batch-toolbar" aria-label="店铺批量操作">
    <span class="shop-batch-toolbar__selection">
      已选择 <strong>{{ selectedCount }}</strong> 家店铺
    </span>
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

</style>
