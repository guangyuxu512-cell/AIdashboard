<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NAlert } from 'naive-ui'
import {
  ManagementListSection,
  EmptyState,
  ErrorState,
  LoadingState,
  TableToolbar,
} from '@/shared/components'
import { AppButton } from '@/shared/ui'
import type { SelectionService } from '../model/contracts'
import { runWindow, runResult } from '../model/run-display'
import StrategyDrawer from './StrategyDrawer.vue'

const props = defineProps<{ service: SelectionService; contextKey: string }>()
const show = ref(false)
const capability = useQuery({
  queryKey: computed(() => ['selection-capabilities', props.contextKey]),
  queryFn: () => props.service.manual!.capabilities(),
  retry: false,
})
const latest = useQuery({
  queryKey: computed(() => ['selection-manual-run', props.contextKey]),
  queryFn: () => props.service.latestRun!(null),
  retry: false,
  refetchInterval: (query) =>
    ['pending', 'running'].includes(query.state.data?.status ?? '')
      ? 2000
      : false,
})
const active = computed(() =>
  ['pending', 'running'].includes(latest.data.value?.status ?? ''),
)
</script>

<template>
  <div class="selection-panel">
    <ManagementListSection>
      <TableToolbar>
        <template #actions>
          <AppButton
            tone="primary"
            :disabled="
              !capability.data.value?.manual_execution_available || active
            "
            @click="show = true"
            >执行选品</AppButton
          >
          <AppButton @click="latest.refetch()">刷新结果</AppButton>
        </template>
      </TableToolbar>
      <ErrorState
        v-if="capability.isError.value"
        description="手动获取状态读取失败"
        retryable
        @retry="capability.refetch()"
      />
      <NAlert
        v-else-if="
          !capability.isPending.value &&
          !capability.data.value?.manual_execution_available
        "
        type="warning"
        >此环境手动获取未启用，已入库结果仍可查询</NAlert
      >
      <LoadingState
        v-if="latest.isPending.value"
        description="正在读取获取记录…"
      />
      <ErrorState
        v-else-if="latest.isError.value"
        description="获取进度查询失败"
        retryable
        @retry="latest.refetch()"
      />
      <NAlert
        v-else-if="latest.data.value"
        :type="
          latest.data.value.status === 'failed' ||
          latest.data.value.status === 'interrupted'
            ? 'error'
            : latest.data.value.status === 'partial'
              ? 'warning'
              : 'info'
        "
      >
        {{ runResult(latest.data.value) }}<br />{{
          runWindow(latest.data.value)
        }}
      </NAlert>
      <EmptyState v-else description="尚未手动获取选品结果" />
    </ManagementListSection>
    <StrategyDrawer
      v-model:show="show"
      :strategy="null"
      :service="service"
      :context-key="contextKey"
      manual-only
      @retrieved="latest.refetch()"
    />
  </div>
</template>
