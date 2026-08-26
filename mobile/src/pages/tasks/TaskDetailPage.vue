<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Collapse as VanCollapse,
  CollapseItem as VanCollapseItem,
  Empty as VanEmpty,
  NoticeBar as VanNoticeBar,
  Progress as VanProgress,
  Skeleton as VanSkeleton,
} from 'vant'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import { useDeviceDetailQuery } from '@/entities/device'
import {
  resolveExecutionName,
  TaskStatusTag,
  useTaskDetailQuery,
} from '@/entities/task'
import {
  deriveCurrentTaskMessage,
  deriveTaskProgress,
  formatTaskDateTime,
  formatTaskDuration,
  TaskOutcomeNotice,
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
const runtime = useTaskRuntime(taskId, taskStatus)
const runtimeNow = useTaskRuntimeClock(
  () => task.value?.started_at ?? null,
  () => task.value?.finished_at ?? null,
)
const expanded = ref<string[]>([])

const executionName = computed(() =>
  task.value
    ? resolveExecutionName({
        execution_display_name: task.value.execution_display_name,
        skill_id: task.value.skill_id,
      })
    : '',
)
const progress = computed(() => deriveTaskProgress(runtime.events.value))
const currentMessage = computed(
  () => deriveCurrentTaskMessage(runtime.events.value) || '暂无运行信息',
)
const progressPercentage = computed(() => {
  if (!progress.value?.total || progress.value.total <= 0) return 0
  return Math.min(
    100,
    Math.max(0, (progress.value.current / progress.value.total) * 100),
  )
})
const progressText = computed(() => {
  if (!progress.value) return '—'
  return progress.value.total === null
    ? String(progress.value.current)
    : `${progress.value.current} / ${progress.value.total}`
})
const runtimeError = computed(() => {
  const error = runtime.eventQuery.error.value
  return error instanceof Error ? error.message : null
})
const detailErrorMessage = computed(() => {
  const error = taskQuery.error.value
  return error instanceof Error ? error.message : '任务详情刷新失败'
})
const durationText = computed(() =>
  formatTaskDuration(
    task.value?.started_at ?? null,
    task.value?.finished_at ?? null,
    runtimeNow.value,
  ),
)
</script>

<template>
  <AppPage class="task-detail-page">
    <div v-if="taskQuery.isPending.value" data-testid="detail-loading">
      <VanSkeleton title :row="8" />
    </div>

    <VanEmpty
      v-else-if="!task"
      image="error"
      :description="
        taskQuery.error.value instanceof Error
          ? taskQuery.error.value.message
          : '任务详情加载失败'
      "
    >
      <VanButton type="primary" @click="taskQuery.refetch()"
        >重新加载</VanButton
      >
    </VanEmpty>

    <template v-else>
      <VanNoticeBar
        v-if="taskQuery.isError.value"
        type="warning"
        :text="`${detailErrorMessage}，当前展示上次成功加载的数据`"
        wrapable
      />
      <section class="task-detail-page__summary" data-testid="task-detail">
        <div class="task-detail-page__title">
          <h1>{{ executionName }}</h1>
          <TaskStatusTag :status="task.status" />
        </div>

        <VanCellGroup inset>
          <VanCell title="设备">
            <template #value>
              <span v-if="deviceQuery.data.value">
                {{ deviceQuery.data.value.display_name }}
              </span>
              <span v-else-if="deviceQuery.isError.value"
                >设备信息加载失败</span
              >
              <span v-else>加载中</span>
            </template>
          </VanCell>
          <VanCell
            title="创建时间"
            :value="formatTaskDateTime(task.created_at)"
          />
          <VanCell
            title="开始时间"
            :value="formatTaskDateTime(task.started_at)"
          />
          <VanCell
            title="结束时间"
            :value="formatTaskDateTime(task.finished_at)"
          />
          <VanCell title="运行耗时" :value="durationText" />
          <VanCell title="店铺数量" :value="`${task.shop_ids.length} 个`" />
        </VanCellGroup>

        <div class="task-detail-page__runtime-summary">
          <div class="task-detail-page__runtime-heading">
            <span>结构化进度</span>
            <span data-testid="detail-progress-value">{{ progressText }}</span>
          </div>
          <VanProgress
            v-if="progress?.total !== null && progress"
            :percentage="progressPercentage"
            :show-pivot="false"
            stroke-width="8"
          />
          <p>{{ currentMessage }}</p>
        </div>

        <TaskOutcomeNotice
          :status="task.status"
          :result="task.result"
          :error-message="task.error_message"
          :error-code="task.error_code"
        />

        <VanCollapse v-model="expanded">
          <VanCollapseItem title="更多信息" name="ids">
            <dl class="task-detail-page__ids">
              <div>
                <dt>任务 ID</dt>
                <dd>{{ task.task_id }}</dd>
              </div>
              <div>
                <dt>技能 ID</dt>
                <dd>{{ task.skill_id }}</dd>
              </div>
              <div>
                <dt>设备 ID</dt>
                <dd>{{ task.target_device_id }}</dd>
              </div>
            </dl>
          </VanCollapseItem>
        </VanCollapse>
      </section>

      <TaskRuntimeLog
        :events="runtime.events.value"
        :initialized="runtime.initialized.value"
        :purged-at="task.runtime_events_purged_at"
        :loading="runtime.eventQuery.isPending.value"
        :loading-earlier="runtime.loadingEarlier.value"
        :has-more-before="runtime.hasMoreBefore.value"
        :initial-error="runtime.events.value.length === 0 ? runtimeError : null"
        :background-error="
          runtime.backgroundError.value ||
          (runtime.events.value.length > 0 ? runtimeError : null)
        "
        :earlier-error="runtime.earlierError.value"
        :reached-memory-limit="runtime.reachedMemoryLimit.value"
        @retry="runtime.eventQuery.refetch"
        @retry-live="runtime.requestDrain"
        @load-earlier="runtime.loadEarlier"
      />
    </template>
  </AppPage>
</template>

<style scoped>
.task-detail-page {
  padding-bottom: var(--space-6);
}

.task-detail-page__summary {
  display: grid;
  gap: var(--space-3);
}

.task-detail-page__title {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  justify-content: space-between;
}

.task-detail-page__title h1 {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-title);
  line-height: var(--line-height-title);
}

.task-detail-page__runtime-summary {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--bg-surface);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-surface);
}

.task-detail-page__runtime-heading {
  display: flex;
  justify-content: space-between;
  color: var(--text-secondary);
}

.task-detail-page__runtime-summary p {
  overflow-wrap: anywhere;
}

.task-detail-page__ids {
  display: grid;
  gap: var(--space-2);
  margin: 0;
}

.task-detail-page__ids div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: var(--space-2);
}

.task-detail-page__ids dt {
  color: var(--text-secondary);
}

.task-detail-page__ids dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
