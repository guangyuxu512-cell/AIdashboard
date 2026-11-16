<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  Skeleton as VanSkeleton,
} from 'vant'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useDeviceDetailQuery } from '@/entities/device'
import { useTaskDetailQuery } from '@/entities/task'
import {
  TaskDetailCard,
  type TaskDetailDeviceState,
  TaskRuntimeLog,
  useTaskRuntime,
  useTaskRuntimeClock,
} from '@/features/task-runtime'
import { AppPage } from '@/shared/ui'

const route = useRoute()
const taskId = computed(() => String(route.params.taskId ?? ''))
const taskQuery = useTaskDetailQuery(taskId)
const task = computed(() => taskQuery.data.value)
const deviceId = computed(() => task.value?.target_device_id)
const deviceQuery = useDeviceDetailQuery(deviceId)
const taskStatus = computed(() => task.value?.status)
const runtime = useTaskRuntime(taskId, taskStatus, () => Boolean(task.value))
const runtimeNow = useTaskRuntimeClock(
  () => task.value?.started_at ?? null,
  () => task.value?.finished_at ?? null,
)
const runtimeRequestFailed = computed(() => runtime.eventQuery.isError.value)
const deviceState = computed<TaskDetailDeviceState>(() => {
  if (deviceQuery.data.value) return 'ready'
  if (deviceQuery.isError.value) return 'error'
  return 'loading'
})
</script>

<template>
  <AppPage
    class="task-detail-page"
    label="任务详情内容"
    data-testid="task-detail-page"
  >
    <div
      v-if="taskQuery.isLoading.value"
      class="task-detail-page__initial-state"
      data-testid="detail-loading"
    >
      <VanSkeleton title :row="6" />
    </div>

    <VanEmpty
      v-else-if="!task"
      class="task-detail-page__initial-state"
      image="error"
      description="加载失败"
      data-testid="task-detail-error"
    >
      <VanButton type="primary" @click="taskQuery.refetch()">重试</VanButton>
    </VanEmpty>

    <div v-else class="task-detail-page__content">
      <TaskDetailCard
        :task="task"
        :device-name="deviceQuery.data.value?.display_name"
        :device-state="deviceState"
        :now="runtimeNow"
      />
      <TaskRuntimeLog
        :events="runtime.events.value"
        :initialized="runtime.initialized.value"
        :purged-at="task.runtime_events_purged_at"
        :loading="runtime.eventQuery.isLoading.value"
        :loading-earlier="runtime.loadingEarlier.value"
        :has-more-before="runtime.hasMoreBefore.value"
        :initial-error="
          runtime.events.value.length === 0 && runtimeRequestFailed
        "
        :background-error="
          Boolean(runtime.backgroundError.value) ||
          (runtime.events.value.length > 0 && runtimeRequestFailed)
        "
        :earlier-error="Boolean(runtime.earlierError.value)"
        :reached-memory-limit="runtime.reachedMemoryLimit.value"
        @retry="runtime.eventQuery.refetch"
        @retry-live="runtime.requestDrain"
        @load-earlier="runtime.loadEarlier"
      />
    </div>
  </AppPage>
</template>

<style scoped>
.task-detail-page.app-page {
  gap: 0;
  padding: var(--visual-v2-detail-content-padding-top)
    max(var(--visual-v2-detail-content-padding-x), var(--safe-area-right))
    var(--visual-v2-detail-content-padding-bottom)
    max(var(--visual-v2-detail-content-padding-x), var(--safe-area-left));
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  background: transparent;
}

.task-detail-page.app-page > .task-detail-page__content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: var(--visual-v2-detail-section-gap);
  overflow: hidden;
}

.task-detail-page__initial-state {
  min-height: var(--layout-inline-state-min-height);
}
</style>
