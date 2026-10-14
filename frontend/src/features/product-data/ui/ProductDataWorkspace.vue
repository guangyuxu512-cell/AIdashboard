<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiMode } from '@/shared/api'
import { PageSection, LoadingState, ErrorState } from '@/shared/components'
import { useAuthStore } from '@/stores/auth'
import { createProductDataSource } from '../api/product-data-source'
import type { ProductDataSource } from '../model/types'
import ProductDataView from './ProductDataView.vue'

const auth = useAuthStore(),
  route = useRoute()
const contextKey = computed(
  () =>
    (auth.currentUser?.userId ?? 'none') + ':' + (auth.activeTeamId ?? 'none'),
)
const source = shallowRef<ProductDataSource | null>(null),
  error = shallowRef<string | null>(null)
let revision = 0
async function load() {
  const generation = ++revision
  source.value = null
  error.value = null
  try {
    const next = await createProductDataSource(
      apiMode,
      typeof route.query.productDataPreview === 'string'
        ? route.query.productDataPreview
        : undefined,
    )
    if (generation === revision) source.value = next
  } catch {
    if (generation === revision) error.value = '商品数据页面加载失败'
  }
}
watch(contextKey, load, { immediate: true, flush: 'sync' })
</script>

<template>
  <PageSection v-if="error" fill
    ><ErrorState :description="error" retryable @retry="load"
  /></PageSection>
  <PageSection v-else-if="!source" fill><LoadingState /></PageSection>
  <ProductDataView
    v-else
    :key="contextKey"
    :source="source"
    :context-key="contextKey"
    :user-id="auth.currentUser?.userId ?? null"
  />
</template>
