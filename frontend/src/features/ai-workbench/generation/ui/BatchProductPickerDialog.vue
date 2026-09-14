<script setup lang="ts">
import { Folder } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppCheckbox, AppDialog, AppInput } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import type { GenerationProductView } from '../model/types'
import { countGenerationProductSourceAssets } from '../model/product-source-assets'

const props = defineProps<{
  show: boolean
  products: GenerationProductView[]
  selectedProductIds: string[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [productIds: string[]]
}>()

const searchDraft = ref('')
const search = ref('')
const autoSearch = useAutoSearch(() => {
  search.value = searchDraft.value
})
const page = ref(1)
const pageSize = ref(10)
const localSelectedIds = ref<string[]>([])

const filteredProducts = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return props.products.filter(
    (product) => !query || product.name.toLocaleLowerCase().includes(query),
  )
})
const visibleProducts = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredProducts.value.slice(start, start + pageSize.value)
})
const visibleIds = computed(() =>
  visibleProducts.value.map((product) => product.id),
)
const visibleSelectedCount = computed(() => {
  const selected = new Set(localSelectedIds.value)
  return visibleIds.value.filter((id) => selected.has(id)).length
})
const currentPageChecked = computed(
  () =>
    visibleIds.value.length > 0 &&
    visibleSelectedCount.value === visibleIds.value.length,
)
const currentPageIndeterminate = computed(
  () => visibleSelectedCount.value > 0 && !currentPageChecked.value,
)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    autoSearch.cancel()
    searchDraft.value = ''
    search.value = ''
    page.value = 1
    pageSize.value = 10
    localSelectedIds.value = [...props.selectedProductIds]
  },
  { immediate: true },
)

watch(search, () => {
  page.value = 1
})

function toggleProduct(productId: string, selected: boolean): void {
  const next = new Set(localSelectedIds.value)
  if (selected) next.add(productId)
  else next.delete(productId)
  localSelectedIds.value = [...next]
}

function toggleProductFromRow(productId: string): void {
  toggleProduct(productId, !localSelectedIds.value.includes(productId))
}

function toggleCurrentPage(selected: boolean): void {
  const next = new Set(localSelectedIds.value)
  visibleIds.value.forEach((id) => {
    if (selected) next.add(id)
    else next.delete(id)
  })
  localSelectedIds.value = [...next]
}

function setPageSize(value: number): void {
  pageSize.value = value
  page.value = 1
}

function confirm(): void {
  emit('confirm', [...localSelectedIds.value])
  emit('update:show', false)
}
</script>

<template>
  <AppDialog
    :show="show"
    title="选择产品"
    size="lg"
    positive-text="确定"
    @update:show="$emit('update:show', $event)"
    @confirm="confirm"
  >
    <div class="batch-product-picker">
      <div class="batch-product-picker__toolbar">
        <AppInput
          v-model="searchDraft"
          clearable
          placeholder="搜索产品"
          aria-label="搜索产品"
          @update:model-value="autoSearch.onInput"
          @compositionstart="autoSearch.onCompositionStart"
          @compositionend="autoSearch.onCompositionEnd(searchDraft)"
          @keyup.enter="autoSearch.onEnter($event)"
        />
        <AppCheckbox
          :model-value="currentPageChecked"
          :indeterminate="currentPageIndeterminate"
          @update:model-value="toggleCurrentPage"
        >
          全选当前页
        </AppCheckbox>
      </div>
      <div v-if="visibleProducts.length" class="batch-product-picker__list">
        <CompactEntityRow
          v-for="product in visibleProducts"
          :key="product.id"
          :title="product.name"
          :count="`商品原图 ${countGenerationProductSourceAssets(product)}`"
          :active="localSelectedIds.includes(product.id)"
          :select-label="`选择产品 ${product.name}`"
          @select="toggleProductFromRow(product.id)"
        >
          <template #icon><Folder :size="16" /></template>
          <template #actions>
            <AppCheckbox
              :model-value="localSelectedIds.includes(product.id)"
              :aria-label="`选择 ${product.name}`"
              @update:model-value="toggleProduct(product.id, $event)"
            />
          </template>
        </CompactEntityRow>
      </div>
      <EmptyState v-else description="暂无产品" />
      <PaginationBar
        v-model:page="page"
        :page-size="pageSize"
        :item-count="filteredProducts.length"
        @update:page-size="setPageSize"
      />
    </div>
  </AppDialog>
</template>

<style scoped>
.batch-product-picker {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.batch-product-picker__toolbar {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.batch-product-picker__list {
  min-height: calc(var(--table-row-height) * 5);
  max-height: calc(var(--table-row-height) * 8);
  overflow-y: auto;
}
</style>
