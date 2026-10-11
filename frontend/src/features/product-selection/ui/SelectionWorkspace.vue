<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useMessage } from 'naive-ui'
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
import type {
  SelectionExecutionSummary,
  SelectionService,
} from '../model/contracts'
import { runResult, runWindow } from '../model/run-display'
import CandidatePool from './CandidatePool.vue'
import StrategyList from './StrategyList.vue'

defineProps<{
  panel: 'candidate-pool' | 'selection-strategy' | 'collection-tasks'
}>()
const auth = useAuthStore()
const message = useMessage()
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
// The workspace survives panel changes. Track only a run submitted here, not
// historical latest runs; leaving this workspace or changing actor clears it.
const submittedRunId = ref<string | null>(null)
watch(
  contextKey,
  () => {
    submittedRunId.value = null
  },
  { flush: 'sync' },
)
const feedback = useQuery({
  queryKey: computed(() => [
    'selection-submitted-run',
    contextKey.value,
    submittedRunId.value,
  ]),
  enabled: computed(() => !!submittedRunId.value && !!service.value?.run),
  queryFn: ({ queryKey }) => service.value!.run!(String(queryKey[2])),
  retry: false,
  refetchInterval: (query) =>
    ['pending', 'running'].includes(query.state.data?.status ?? '')
      ? 1000
      : false,
})
function notify(execution: SelectionExecutionSummary) {
  if (
    execution.run_id !== submittedRunId.value ||
    ['pending', 'running'].includes(execution.status)
  )
    return
  submittedRunId.value = null
  const text = `${runResult(execution)} · ${runWindow(execution)}`
  if (['failed', 'interrupted'].includes(execution.status)) message.error(text)
  else if (execution.status === 'partial') message.warning(text)
  else message.success(text)
}
function submitted(execution: SelectionExecutionSummary) {
  submittedRunId.value = execution.run_id
  notify(execution)
}
function refreshFeedback() {
  if (submittedRunId.value) void feedback.refetch()
}
watch(feedback.data, (execution) => {
  if (execution) notify(execution)
})
watch(feedback.error, (error) => {
  if (error && submittedRunId.value)
    message.error('获取进度查询失败，请刷新重试')
})
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
      !service.manual &&
      !(panel === 'candidate-pool' && service.candidatesAvailable)
    "
    ><EmptyState :description="SELECTION_UNAVAILABLE"
  /></PageSection>
  <CandidatePool
    v-else-if="panel === 'candidate-pool'"
    :key="`pool:${contextKey}`"
    :service="service"
    :context-key="contextKey"
    @refresh-run-feedback="refreshFeedback"
  />
  <StrategyList
    v-else
    :key="`strategy:${contextKey}`"
    :service="service"
    :context-key="contextKey"
    @submitted="submitted"
    @refresh-run-feedback="refreshFeedback"
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
