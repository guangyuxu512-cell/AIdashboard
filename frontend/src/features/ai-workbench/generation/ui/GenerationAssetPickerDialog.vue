<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { AssetContentImage } from '@/entities/asset'
import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { AppDialog, AppSelect } from '@/shared/ui'

import type {
  GenerationProductView,
  GenerationSourceImageView,
  GenerationSourceRole,
} from '../model/types'

const props = defineProps<{
  show: boolean
  products: GenerationProductView[]
  role: GenerationSourceRole
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [source: GenerationSourceImageView]
}>()

const selectedProductId = ref<string | null>(null)
const selectedAssetId = ref<string | null>(null)

const productOptions = computed(() =>
  props.products
    .filter((product) =>
      product.assets.some((asset) => asset.role === props.role),
    )
    .map((product) => ({ label: product.name, value: product.id })),
)

const selectedProduct = computed(
  () =>
    props.products.find((product) => product.id === selectedProductId.value) ??
    null,
)

const visibleAssets = computed(
  () =>
    selectedProduct.value?.assets.filter(
      (asset) => asset.role === props.role,
    ) ?? [],
)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    selectedProductId.value = productOptions.value[0]?.value ?? null
    selectedAssetId.value = null
  },
  { immediate: true },
)

watch(productOptions, (options) => {
  if (
    props.show &&
    !options.some((option) => option.value === selectedProductId.value)
  ) {
    selectedProductId.value = options[0]?.value ?? null
  }
})

watch(selectedProductId, () => {
  selectedAssetId.value = null
})

function confirm(): void {
  const source = visibleAssets.value.find(
    (asset) => asset.id === selectedAssetId.value,
  )
  if (!source) return
  emit('confirm', { ...source })
  emit('update:show', false)
}
</script>

<template>
  <AppDialog
    :show="show"
    :title="role === 'PRODUCT_SOURCE' ? '选择商品图片' : '选择复刻参考'"
    size="lg"
    positive-text="选择"
    :positive-disabled="!selectedAssetId"
    @update:show="$emit('update:show', $event)"
    @confirm="confirm"
  >
    <div class="generation-asset-picker">
      <AppSelect
        v-model="selectedProductId"
        :options="productOptions"
        placeholder="选择产品"
        aria-label="产品素材组"
      />
      <div v-if="visibleAssets.length" class="generation-asset-picker__list">
        <CompactEntityRow
          v-for="asset in visibleAssets"
          :key="asset.id"
          :title="asset.name"
          count=""
          :active="selectedAssetId === asset.id"
          :select-label="`选择素材 ${asset.name}`"
          @select="selectedAssetId = asset.id"
        >
          <template #icon>
            <AssetContentImage
              class="generation-asset-picker__thumbnail"
              :src="asset.thumbnailUrl ?? asset.previewUrl"
              :alt="asset.name"
            />
          </template>
        </CompactEntityRow>
      </div>
      <EmptyState v-else description="暂无可选素材" />
    </div>
  </AppDialog>
</template>

<style scoped>
.generation-asset-picker {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}

.generation-asset-picker__list {
  max-height: calc(var(--dialog-max-height) - var(--field-width-md));
  overflow-y: auto;
}

.generation-asset-picker__thumbnail {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  object-fit: cover;
}
</style>
