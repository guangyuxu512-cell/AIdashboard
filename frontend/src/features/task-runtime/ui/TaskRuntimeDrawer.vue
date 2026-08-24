<script setup lang="ts">
import dayjs from 'dayjs'
import { NCollapse, NCollapseItem } from 'naive-ui'
import { computed, nextTick, ref, watch } from 'vue'

import { TaskStatusTag } from '@/entities/task'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import { isLogViewportNearEnd } from '../model/log-follow'
import {
  getCurrentRuntimeMessage,
  getLatestProgressEvent,
  getProgressDisplay,
  summarizeTaskFailure,
  summarizeTaskResult,
} from '../model/task-runtime-display'
import { useTaskRuntime } from '../model/useTaskRuntime'

const props = defineProps<{
  show: boolean
  taskId: string | null
  deviceName?: string | null
}>()

defineEmits<{ 'update:show': [value: boolean] }>()

const runtime = useTaskRuntime(
  computed(() => (props.show ? props.taskId : null)),
)
const logViewport = ref<HTMLElement | null>(null)
const autoFollow = ref(true)
const providerDisplay = computed(() => {
  const provider = runtime.metadata.value.provider
  return provider === 'yingdao'
    ? '影刀'
    : provider === 'python'
      ? 'Python'
      : typeof provider === 'string'
        ? provider
        : '—'
})
const latestProgress = computed(() =>
  getLatestProgressEvent(runtime.events.value),
)
const progressDisplay = computed(() =>
  getProgressDisplay(latestProgress.value),
)
const currentMessage = computed(() =>
  getCurrentRuntimeMessage(runtime.events.value),
)
const resultSummary = computed(() => {
  const task = runtime.task.value
  return task ? summarizeTaskResult(task.status, task.result) : null
})
const failureSummary = computed(() => {
  const task = runtime.task.value
  return task ? summarizeTaskFailure(task) : null
})
const applicationId = computed(() => {
  const appId = runtime.task.value?.input.app_id
  return typeof appId === 'string' ? appId : null
})

function resultValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

function formatTime(value: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
}

function onLogScroll(): void {
  const element = logViewport.value
  if (!element) return
  autoFollow.value = isLogViewportNearEnd(
    element.scrollHeight,
    element.scrollTop,
    element.clientHeight,
  )
}

async function scrollToLatest(): Promise<void> {
  autoFollow.value = true
  await nextTick()
  const element = logViewport.value
  if (element) element.scrollTop = element.scrollHeight
}

watch(
  () => runtime.events.value.length,
  async () => {
    if (autoFollow.value) await scrollToLatest()
  },
)

watch(
  () => props.taskId,
  () => {
    autoFollow.value = true
  },
)
</script>

<template>
  <DetailDrawer
    :show="show"
    title="运行详情"
    size="lg"
    body-content-class="task-runtime-drawer__body"
    @update:show="$emit('update:show', $event)"
  >
    <LoadingState
      v-if="runtime.loading.value"
      description="正在读取运行详情…"
    />
    <ErrorState
      v-else-if="runtime.error.value"
      description="运行详情加载失败"
      retryable
      @retry="runtime.retry"
    />
    <div v-else-if="runtime.task.value" class="task-runtime">
      <dl class="task-runtime__facts">
        <div>
          <dt>执行对象</dt>
          <dd>{{ runtime.task.value.execution_display_name }}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd><TaskStatusTag :status="runtime.task.value.status" /></dd>
        </div>
        <div>
          <dt>设备</dt>
          <dd>{{ deviceName ?? runtime.task.value.target_device_id }}</dd>
        </div>
        <div v-if="runtime.task.value.status === 'pending'">
          <dt>创建时间</dt>
          <dd>{{ formatTime(runtime.task.value.created_at) }}</dd>
        </div>
        <template v-else>
          <div>
            <dt>开始时间</dt>
            <dd>{{ formatTime(runtime.task.value.started_at) }}</dd>
          </div>
          <div>
            <dt>{{ runtime.terminal.value ? '耗时' : '运行时间' }}</dt>
            <dd>{{ runtime.durationDisplay.value }}</dd>
          </div>
        </template>
        <div v-if="latestProgress">
          <dt>进度</dt>
          <dd>{{ progressDisplay }}</dd>
        </div>
        <div v-if="runtime.task.value.status !== 'pending'">
          <dt>当前信息</dt>
          <dd>{{ currentMessage }}</dd>
        </div>
        <div v-if="runtime.terminal.value">
          <dt>结束时间</dt>
          <dd>{{ formatTime(runtime.task.value.finished_at) }}</dd>
        </div>
      </dl>

      <section v-if="resultSummary" class="task-runtime__outcome">
        <h3>执行结果</h3>
        <p>{{ resultSummary.summary }}</p>
        <dl v-if="resultSummary.fields.length">
          <div v-for="([key, value], index) in resultSummary.fields" :key="index">
            <dt>{{ key }}</dt>
            <dd>{{ resultValue(value) }}</dd>
          </div>
        </dl>
      </section>

      <section v-else-if="failureSummary" class="task-runtime__outcome task-runtime__outcome--error">
        <h3>失败原因</h3>
        <p>{{ failureSummary.message }}</p>
        <small v-if="failureSummary.code">错误码：{{ failureSummary.code }}</small>
      </section>

      <NCollapse class="task-runtime__more">
        <NCollapseItem title="更多信息" name="technical">
          <dl>
            <div>
              <dt>Task ID</dt>
              <dd>{{ runtime.task.value.task_id }}</dd>
            </div>
            <div>
              <dt>Skill ID</dt>
              <dd>{{ runtime.task.value.skill_id }}</dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{{ providerDisplay }}</dd>
            </div>
            <div>
              <dt>Device UUID</dt>
              <dd>{{ runtime.task.value.target_device_id }}</dd>
            </div>
            <div v-if="applicationId">
              <dt>Application UUID</dt>
              <dd>{{ applicationId }}</dd>
            </div>
            <div v-if="runtime.metadata.value.yingdao_task_uuid">
              <dt>影刀 Task UUID</dt>
              <dd>{{ runtime.metadata.value.yingdao_task_uuid }}</dd>
            </div>
          </dl>
        </NCollapseItem>
      </NCollapse>

      <section class="task-runtime__logs">
        <header>
          <h3>运行日志</h3>
          <div class="task-runtime__log-actions">
            <AppButton
              v-if="
                runtime.hasEarlier.value && !runtime.historyLimitReached.value
              "
              tone="text"
              :loading="runtime.loadingEarlier.value"
              @click="runtime.loadEarlier"
            >
              加载更早
            </AppButton>
            <AppButton v-if="!autoFollow" tone="text" @click="scrollToLatest">
              回到最新
            </AppButton>
          </div>
        </header>
        <p v-if="runtime.purgedAt.value" class="task-runtime__retention-notice">
          {{
            runtime.events.value.length
              ? '部分历史运行日志已按保留策略清理。'
              : '该任务的历史运行日志已按保留策略清理。'
          }}
          清理时间：{{ formatTime(runtime.purgedAt.value) }}
        </p>
        <p
          v-if="runtime.historyLimitReached.value"
          class="task-runtime__retention-notice"
        >
          为保持运行详情流畅，当前最多显示最近 1000 条日志。
        </p>
        <p
          v-if="runtime.historyError.value"
          class="task-runtime__history-error"
        >
          更早日志加载失败，请重试。
        </p>
        <div
          ref="logViewport"
          class="task-runtime__log-viewport"
          @scroll="onLogScroll"
        >
          <ol v-if="runtime.events.value.length">
            <li v-for="event in runtime.events.value" :key="event.seq">
              <time>{{ dayjs(event.event_at).format('HH:mm:ss') }}</time>
              <span class="task-runtime__level">{{ event.level }}</span>
              <span>{{ event.message }}</span>
            </li>
          </ol>
          <EmptyState
            v-else
            :description="
              runtime.purgedAt.value
                ? '该任务的历史运行日志已按保留策略清理。'
                : '暂无运行日志'
            "
          />
        </div>
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
:global(.task-runtime-drawer__body) {
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.task-runtime {
  display: flex;
  min-height: 0;
  width: 100%;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
}

.task-runtime__facts {
  display: grid;
  margin: 0;
  flex: none;
  gap: var(--space-3) var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-runtime__facts div,
.task-runtime__more dl div,
.task-runtime__outcome dl div {
  min-width: 0;
}

.task-runtime dt {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.task-runtime dd {
  margin: var(--space-1) 0 0;
  overflow-wrap: anywhere;
}

.task-runtime__outcome {
  flex: none;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.task-runtime__outcome h3,
.task-runtime__logs h3 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.task-runtime__outcome p {
  margin: var(--space-2) 0 0;
}

.task-runtime__outcome small {
  display: block;
  margin-top: var(--space-1);
  color: var(--text-secondary);
}

.task-runtime__outcome dl,
.task-runtime__more dl {
  display: grid;
  margin: var(--space-3) 0 0;
  gap: var(--space-2) var(--space-4);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-runtime__outcome--error {
  border-color: var(--color-error);
}

.task-runtime__more {
  flex: none;
}

.task-runtime__logs {
  display: flex;
  min-height: 200px;
  flex: 1;
  flex-direction: column;
}

.task-runtime__logs header {
  display: flex;
  min-height: var(--control-height-default);
  flex: none;
  align-items: center;
  justify-content: space-between;
}

.task-runtime__log-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.task-runtime__retention-notice,
.task-runtime__history-error {
  margin: 0 0 var(--space-2);
  padding: var(--space-2) var(--space-3);
  flex: none;
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.task-runtime__history-error {
  color: var(--color-error);
}

.task-runtime__log-viewport {
  min-height: 0;
  overflow: auto;
  flex: 1;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.task-runtime__log-viewport ol {
  margin: 0;
  padding: var(--space-3);
  list-style: none;
}

.task-runtime__log-viewport li {
  display: grid;
  padding: var(--space-1) 0;
  gap: var(--space-2);
  grid-template-columns: auto auto minmax(0, 1fr);
  line-height: var(--line-height-body);
}

.task-runtime__log-viewport time,
.task-runtime__level {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

@media (max-width: 720px) {
  .task-runtime__facts,
  .task-runtime__outcome dl,
  .task-runtime__more dl {
    grid-template-columns: 1fr;
  }
}
</style>
