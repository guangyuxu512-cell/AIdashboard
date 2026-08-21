<script setup lang="ts">
import type { ShopListItemViewModel } from '@/entities/shop'
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  shop: ShopListItemViewModel | null
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
    title="确认移除店铺"
    size="sm"
    positive-text="确认移除"
    negative-text="取消"
    :loading="submitting"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <div class="shop-remove-dialog">
      <p>店铺：<strong>{{ shop?.shopName }}</strong></p>
      <p>
        移除后，该店铺将不再出现在正常业务列表中，设备绑定将停用，但登录凭证、Session
        和历史记录会保留。
      </p>
    </div>
  </AppDialog>
</template>

<style scoped>
.shop-remove-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  color: var(--text-secondary);
  line-height: var(--line-height-body);
}

.shop-remove-dialog strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}
</style>
