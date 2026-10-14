<script setup lang="ts">
import { Copy } from '@lucide/vue'
import { NEllipsis, NTooltip, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { AppButton } from '@/shared/ui'
import ProductImage from './ProductImage.vue'

const props = defineProps<{
  productId: string
  title: string
  imageUrl: string | null
}>()
const message = useMessage(),
  copying = ref(false)
async function copyId() {
  if (copying.value) return
  copying.value = true
  try {
    await navigator.clipboard.writeText(props.productId)
    message.success('商品ID已复制')
  } catch {
    message.error('复制失败，可选中商品ID手动复制')
  } finally {
    copying.value = false
  }
}
</script>

<template>
  <div class="product-info-cell">
    <ProductImage :src="imageUrl" :title="title" size="thumbnail" />
    <div class="product-info-cell__text">
      <NEllipsis :line-clamp="2">{{ title }}</NEllipsis>
      <div class="product-info-cell__id">
        <span :title="productId">{{ productId }}</span>
        <NTooltip>
          <template #trigger>
            <AppButton
              size="small"
              tone="text"
              :loading="copying"
              :disabled="copying"
              aria-label="复制商品ID"
              @click.stop="copyId"
              ><Copy :size="14" aria-hidden="true"
            /></AppButton>
          </template>
          复制商品ID
        </NTooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.product-info-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  text-align: left;
}
.product-info-cell > :first-child {
  flex: 0 0 auto;
}
.product-info-cell__text {
  min-width: 0;
  flex: 1;
}
.product-info-cell__id {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
.product-info-cell__id > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  user-select: text;
}
</style>
