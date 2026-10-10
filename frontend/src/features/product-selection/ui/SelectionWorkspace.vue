<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { apiMode } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'
import {
  EmptyState,
  LoadingState,
  ErrorState,
  PageSection,
} from '@/shared/components'
import {
  createSelectionService,
  SELECTION_UNAVAILABLE,
} from '../api/selection-service'
import type { SelectionService } from '../model/contracts'
import CandidatePool from './CandidatePool.vue'
import StrategyList from './StrategyList.vue'

defineProps<{
  panel: 'candidate-pool' | 'selection-strategy' | 'collection-tasks'
}>()
const auth = useAuthStore()
const contextKey = computed(
  () => `${auth.currentUser?.userId ?? 'none'}:${auth.activeTeamId ?? 'none'}`,
)
const service = shallowRef<SelectionService | null>(null)
const error = shallowRef<string | null>(null)
let revision = 0
async function load() {
  const current = ++revision
  service.value = null
  error.value = null
  try {
    const source = await createSelectionService(apiMode)
    if (current === revision) service.value = source
  } catch (cause) {
    if (current === revision)
      error.value = cause instanceof Error ? cause.message : '加载失败'
  }
}
watch(contextKey, load, { immediate: true })
</script>

<template>
  <PageSection v-if="panel === 'collection-tasks'"
    ><EmptyState description="采集任务功能待接入"
  /></PageSection>
  <PageSection v-else-if="error"
    ><ErrorState :description="error" retryable @retry="load"
  /></PageSection>
  <PageSection v-else-if="!service"><LoadingState /></PageSection>
  <PageSection
    v-else-if="
      !service.available &&
      !(panel === 'candidate-pool' && service.candidatesAvailable)
    "
    ><EmptyState :description="SELECTION_UNAVAILABLE"
  /></PageSection>
  <CandidatePool
    v-else-if="panel === 'candidate-pool'"
    :key="`pool:${contextKey}`"
    :service="service"
    :context-key="contextKey"
  />
  <StrategyList
    v-else
    :key="`strategy:${contextKey}`"
    :service="service"
    :context-key="contextKey"
  />
</template>

<style>
.selection-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}
.selection-row-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
}
</style>
