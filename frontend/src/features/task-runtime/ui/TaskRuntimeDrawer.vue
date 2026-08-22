<script setup lang="ts">
import dayjs from 'dayjs'
import { computed, nextTick, ref, watch } from 'vue'

import { TaskStatusTag } from '@/entities/task'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import { useTaskRuntime } from '../model/useTaskRuntime'
import { isLogViewportNearEnd } from '../model/log-follow'

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
          <dt>任务状态</dt>
          <dd><TaskStatusTag :status="runtime.task.value.status" /></dd>
        </div>
        <div>
          <dt>设备</dt>
          <dd>{{ deviceName ?? runtime.task.value.target_device_id }}</dd>
        </div>
        <div>
          <dt>Skill</dt>
          <dd>{{ runtime.task.value.skill_id }}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{{ providerDisplay }}</dd>
        </div>
        <div>
          <dt>影刀应用</dt>
          <dd>{{ runtime.metadata.value.app_name ?? '—' }}</dd>
        </div>
        <div>
          <dt>影刀 Task UUID</dt>
          <dd>{{ runtime.metadata.value.yingdao_task_uuid ?? '—' }}</dd>
        </div>
        <div>
          <dt>开始时间</dt>
          <dd>
            {{
              dayjs(
                runtime.task.value.started_at ?? runtime.task.value.created_at,
              ).format('YYYY-MM-DD HH:mm:ss')
            }}
          </dd>
        </div>
        <div>
          <dt>运行时间</dt>
          <dd>{{ runtime.durationDisplay.value }}</dd>
        </div>
        <div class="task-runtime__step">
          <dt>当前步骤</dt>
          <dd>
            {{ runtime.events.value.at(-1)?.message ?? '—' }}
          </dd>
        </div>
      </dl>

      <section class="task-runtime__logs">
        <header>
          <h3>运行日志</h3>
          <AppButton v-if="!autoFollow" tone="text" @click="scrollToLatest">
            回到最新
          </AppButton>
        </header>
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
          <EmptyState v-else description="暂无运行日志" />
        </div>
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.task-runtime {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-5);
}

.task-runtime__facts {
  display: grid;
  margin: 0;
  gap: var(--space-3) var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-runtime__facts div {
  min-width: 0;
}

.task-runtime__facts dt {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.task-runtime__facts dd {
  margin: var(--space-1) 0 0;
  overflow-wrap: anywhere;
}

.task-runtime__step {
  grid-column: 1 / -1;
}

.task-runtime__logs {
  min-height: 0;
}

.task-runtime__logs header {
  display: flex;
  min-height: var(--control-height-default);
  align-items: center;
  justify-content: space-between;
}

.task-runtime__logs h3 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.task-runtime__log-viewport {
  height: var(--task-runtime-log-height);
  overflow: auto;
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
  .task-runtime__facts {
    grid-template-columns: 1fr;
  }

  .task-runtime__step {
    grid-column: auto;
  }
}
</style>
