<script setup lang="ts">
import { computed } from 'vue'
import { NList, NListItem, NText } from 'naive-ui'
import { AppDialog } from '@/shared/ui'
import type { LibraryProduct } from '../model/contracts'

const props = defineProps<{
  show: boolean
  products: LibraryProduct[]
}>()
defineEmits<{
  'update:show': [value: boolean]
  confirm: []
}>()

const files = computed(() =>
  props.products.map((product) => `${product.productId}.txt`),
)
</script>

<template>
  <AppDialog
    :show="show"
    title="导出商品资料"
    size="sm"
    positive-text="确认演示"
    :positive-disabled="!products.length"
    positive-disabled-reason="请先选择商品"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <p class="product-export-dialog__summary">
      {{ products.length === 1 ? '单个商品导出 TXT' : '批量商品导出 ZIP' }}
    </p>
    <NList bordered>
      <NListItem v-for="file in files" :key="file">{{ file }}</NListItem>
    </NList>
    <NText depth="3">
      演示模式仅核对导出入口与文件清单，不生成或下载真实文件。正式输出中 .txt 与
      .origin.txt 均为清洗后的兼容文本，不代表原始网络响应。
    </NText>
  </AppDialog>
</template>

<style scoped>
.product-export-dialog__summary {
  margin: 0 0 var(--space-3);
  color: var(--text-primary);
}
</style>
