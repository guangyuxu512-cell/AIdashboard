<script setup lang="ts">
import { Folder, MoreHorizontal, Plus } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import type { ProductMaterialGroup } from '../model/types'
import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

defineProps<{
  products: readonly ProductMaterialGroup[]
  selectedProductId: string | null
}>()

const emit = defineEmits<{
  create: []
  select: [productId: string]
  rename: [product: ProductMaterialGroup]
  remove: [product: ProductMaterialGroup]
}>()

const menuOptions: DropdownOption[] = [
  { key: 'rename', label: '重命名' },
  { key: 'remove', label: '删除' },
]

function selectAction(
  product: ProductMaterialGroup,
  key: string | number,
): void {
  if (key === 'rename') emit('rename', product)
  if (key === 'remove') emit('remove', product)
}
</script>

<template>
  <section class="product-material-sidebar" aria-label="产品文件夹">
    <div class="product-material-sidebar__header">
      <strong>产品</strong>
      <AppButton tone="text" aria-label="新建产品" @click="$emit('create')">
        <Plus :size="16" />
        新建产品
      </AppButton>
    </div>

    <div class="product-material-sidebar__list">
      <EmptyState v-if="products.length === 0" description="暂无产品" />
      <CompactEntityRow
        v-for="product in products"
        v-else
        :key="product.id"
        class="product-material-sidebar__item"
        :title="product.name"
        :count="product.assets.length"
        :active="product.id === selectedProductId"
        :select-label="`选择产品 ${product.name}`"
        :data-product-id="product.id"
        @select="$emit('select', product.id)"
      >
        <template #icon>
          <Folder :size="18" />
        </template>
        <template #status>
          <StatusTag
            appearance="dot"
            :label="product.enabled ? '启用' : '停用'"
            :tone="product.enabled ? 'success' : 'neutral'"
          />
        </template>
        <template #actions>
          <NDropdown
            trigger="click"
            :options="menuOptions"
            @select="selectAction(product, $event)"
          >
            <AppButton tone="text" :aria-label="`${product.name}操作`">
              <MoreHorizontal :size="16" />
            </AppButton>
          </NDropdown>
        </template>
      </CompactEntityRow>
    </div>
  </section>
</template>

<style scoped>
.product-material-sidebar {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.product-material-sidebar__header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.product-material-sidebar__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.product-material-sidebar__list {
  min-height: 0;
  flex: 1;
  padding: var(--space-2);
  overflow-y: auto;
  scrollbar-width: none;
}

.product-material-sidebar__list::-webkit-scrollbar {
  display: none;
}
</style>
