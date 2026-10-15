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
      <NEllipsis>{{ title }}</NEllipsis>
      <div class="product-info-cell__id">
        <NEllipsis
          class="product-info-cell__id-text"
          :tooltip="{
            placement: 'top-start',
            contentStyle: {
              maxWidth: 'var(--field-width-lg)',
              overflowWrap: 'anywhere',
            },
          }"
          >ID：{{ productId }}</NEllipsis
        >
        <NTooltip>
          <template #trigger>
            <AppButton
              class="product-info-cell__copy"
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
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--control-height-compact);
  width: 100%;
  max-width: calc(
    var(--field-width-sm) + var(--space-1) + var(--control-height-compact)
  );
  min-width: 0;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
.product-info-cell__id-text {
  min-width: 0;
  user-select: text;
}
.product-info-cell__copy {
  width: var(--control-height-compact);
  min-width: var(--control-height-compact);
}
</style>
