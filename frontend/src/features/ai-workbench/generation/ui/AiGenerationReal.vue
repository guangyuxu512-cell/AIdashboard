<script setup lang="ts">
import { computed, ref } from 'vue'

import { AiManagementToolbar } from '@/features/ai-workbench'
import { getErrorMessage } from '@/shared/api'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'

import {
  GENERATION_WORK_MODE_META,
  type GenerationWorkMode,
} from '../model/types'
import { useGenerationCatalogs } from '../../real-api/model/useWorkbenchCatalogs'
import BatchGenerationRealPanel from './BatchGenerationRealPanel.vue'
import InstantGenerationRealPanel from './InstantGenerationRealPanel.vue'

const workMode = ref<GenerationWorkMode>('INSTANT')
const catalogs = useGenerationCatalogs()
const models = computed(catalogs.models)
const products = computed(catalogs.products)
const templateGroups = computed(catalogs.templates)
const pending = computed(
  () =>
    catalogs.modelsQuery.isPending.value ||
    catalogs.productsQuery.isPending.value ||
    catalogs.templatesQuery.isPending.value,
)
const error = computed(
  () =>
    catalogs.modelsQuery.error.value ??
    catalogs.productsQuery.error.value ??
    catalogs.templatesQuery.error.value,
)
const workModeOptions = [
  { label: GENERATION_WORK_MODE_META.INSTANT.label, key: 'INSTANT' },
  { label: GENERATION_WORK_MODE_META.BATCH.label, key: 'BATCH' },
]

function reload(): void {
  void catalogs.modelsQuery.refetch()
  void catalogs.productsQuery.refetch()
  void catalogs.templatesQuery.refetch()
}
</script>

<template>
  <AiManagementToolbar label="生成工作方式">
    <span class="ai-generate__work-mode-label">工作方式</span>
    <ContextSwitchBar
      label="生成工作方式"
      appearance="bare"
      :active-key="workMode"
      :items="workModeOptions"
      @select="workMode = $event as GenerationWorkMode"
    />
  </AiManagementToolbar>
  <LoadingState v-if="pending" description="正在加载生成配置" />
  <ErrorState
    v-else-if="error"
    :description="getErrorMessage(error)"
    retryable
    @retry="reload"
  />
  <InstantGenerationRealPanel
    v-else-if="workMode === 'INSTANT'"
    :models="models"
    :products="products"
    :template-groups="templateGroups"
  />
  <BatchGenerationRealPanel
    v-else
    :models="models"
    :products="products"
    :template-groups="templateGroups"
  />
</template>

<style scoped>
.ai-generate__work-mode-label {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-medium);
}
</style>
