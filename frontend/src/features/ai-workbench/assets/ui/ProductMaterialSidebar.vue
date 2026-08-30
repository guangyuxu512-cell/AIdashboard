<script setup lang="ts">
import { MoreHorizontal, Package, Plus } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import type { ProductMaterialGroup } from '../model/types'
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

function thumbnail(product: ProductMaterialGroup): string | null {
  return (
    product.assets.find((asset) => asset.role === 'PRODUCT_SOURCE')
      ?.previewUrl ?? null
  )
}
</script>

<template>
  <section class="product-material-sidebar" aria-label="产品列表">
    <div class="product-material-sidebar__header">
      <strong>产品</strong>
      <AppButton tone="text" aria-label="新建产品" @click="$emit('create')">
        <Plus :size="16" />
        新建产品
      </AppButton>
    </div>

    <div class="product-material-sidebar__list">
      <EmptyState v-if="products.length === 0" description="暂无产品" />
      <article
        v-for="product in products"
        v-else
        :key="product.id"
        class="product-material-sidebar__item"
        :class="{
          'product-material-sidebar__item--active':
            product.id === selectedProductId,
        }"
      >
        <button
          class="product-material-sidebar__select"
          type="button"
          :aria-label="`选择产品 ${product.name}`"
          :aria-pressed="product.id === selectedProductId"
          @click="$emit('select', product.id)"
        >
          <img
            v-if="thumbnail(product)"
            class="product-material-sidebar__thumbnail"
            :src="thumbnail(product) ?? undefined"
            :alt="product.name"
          />
          <span v-else class="product-material-sidebar__thumbnail-fallback">
            <Package :size="18" />
          </span>
          <span class="product-material-sidebar__identity">
            <strong :title="product.name">{{ product.name }}</strong>
            <span v-if="product.sku" :title="product.sku">{{
              product.sku
            }}</span>
          </span>
          <span class="product-material-sidebar__count" aria-label="素材数量">
            {{ product.assets.length }}
          </span>
        </button>
        <div class="product-material-sidebar__meta">
          <StatusTag
            :label="product.enabled ? '启用' : '停用'"
            :tone="product.enabled ? 'success' : 'neutral'"
          />
          <NDropdown
            trigger="click"
            :options="menuOptions"
            @select="selectAction(product, $event)"
          >
            <AppButton
              tone="text"
              :aria-label="`${product.name}操作`"
              @click.stop
            >
              <MoreHorizontal :size="16" />
            </AppButton>
          </NDropdown>
        </div>
      </article>
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

.product-material-sidebar__header,
.product-material-sidebar__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.product-material-sidebar__header {
  flex: 0 0 auto;
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

.product-material-sidebar__item {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
}

.product-material-sidebar__item + .product-material-sidebar__item {
  margin-top: var(--space-1);
}

.product-material-sidebar__item:hover {
  background: var(--bg-surface-hover);
}

.product-material-sidebar__item--active {
  border-color: var(--border-default);
  background: var(--color-primary-soft);
}

.product-material-sidebar__select {
  display: grid;
  min-width: 0;
  padding: var(--space-1);
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  grid-template-columns: var(--control-height-large) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  background: transparent;
}

.product-material-sidebar__thumbnail,
.product-material-sidebar__thumbnail-fallback {
  width: var(--control-height-large);
  height: var(--control-height-large);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.product-material-sidebar__thumbnail {
  display: block;
  object-fit: cover;
}

.product-material-sidebar__thumbnail-fallback {
  display: grid;
  place-items: center;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
}

.product-material-sidebar__identity {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.product-material-sidebar__identity strong,
.product-material-sidebar__identity span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-material-sidebar__identity strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}

.product-material-sidebar__identity span,
.product-material-sidebar__count {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.product-material-sidebar__meta {
  flex-direction: column;
}
</style>
