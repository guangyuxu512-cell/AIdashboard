<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'
import { computed } from 'vue'

import {
  type ScheduleDetailViewModel,
  useScheduleRunsQuery,
} from '@/entities/schedule'
import { TaskStatusTag } from '@/entities/task'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import {
  getErrorMessage,
  isInitialQueryError,
  isInitialQueryLoading,
} from '@/shared/api'

const props = defineProps<{
  show: boolean
  schedule: ScheduleDetailViewModel | null
  loading?: boolean
  error?: string | null
  statusChanging?: boolean
  removing?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  retry: []
  edit: []
  toggle: []
  remove: []
  runtime: [taskId: string, deviceName: string]
}>()

const scheduleId = computed(() => props.schedule?.scheduleId ?? null)
const timezone = computed(() => props.schedule?.timezone ?? 'Asia/Shanghai')
const runsQuery = useScheduleRunsQuery(scheduleId, timezone)
const runs = computed(() => runsQuery.data.value?.items ?? [])
const runsLoading = computed(() =>
  isInitialQueryLoading(runsQuery.isPending.value, runsQuery.data.value),
)
const runsError = computed(() =>
  isInitialQueryError(runsQuery.error.value, runsQuery.data.value)
    ? getErrorMessage(runsQuery.error.value)
    : null,
)

function parameterDisplay(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}
</script>

<template>
  <DetailDrawer
    :show="show"
    title="定时计划详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <template v-if="schedule" #header>
      <div class="schedule-detail-header">
        <strong>{{ schedule.name }}</strong>
        <StatusTag
          :label="schedule.enabled ? '已开启' : '已停用'"
          :tone="schedule.enabled ? 'success' : 'neutral'"
        />
      </div>
    </template>

    <LoadingState v-if="loading" description="正在加载定时计划…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <div v-else-if="schedule" class="schedule-detail">
      <section>
        <h3>计划信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="执行对象">
            {{ schedule.executionName }}
          </NDescriptionsItem>
          <NDescriptionsItem label="执行设备">
            {{ schedule.deviceName }}
          </NDescriptionsItem>
          <NDescriptionsItem label="触发规则">
            {{ schedule.triggerRuleDisplay }}
          </NDescriptionsItem>
          <NDescriptionsItem label="时区">
            {{ schedule.timezone }}
          </NDescriptionsItem>
          <NDescriptionsItem label="下次执行">
            {{ schedule.nextRunAtDisplay }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>应用参数</h3>
        <NDescriptions
          v-if="Object.keys(schedule.parameters).length"
          :column="1"
          label-placement="left"
          bordered
        >
          <NDescriptionsItem
            v-for="(value, key) in schedule.parameters"
            :key="key"
            :label="key"
          >
            {{ parameterDisplay(value) }}
          </NDescriptionsItem>
        </NDescriptions>
        <EmptyState v-else description="该应用没有配置输入参数" />
      </section>

      <section>
        <h3>执行历史</h3>
        <LoadingState v-if="runsLoading" description="正在读取执行历史…" />
        <ErrorState
          v-else-if="runsError"
          :description="runsError"
          retryable
          @retry="runsQuery.refetch()"
        />
        <ul v-else-if="runs.length" class="schedule-runs">
          <li v-for="run in runs" :key="run.runId">
            <span>{{ run.scheduledForDisplay }}</span>
            <TaskStatusTag v-if="run.taskStatus" :status="run.taskStatus" />
            <StatusTag v-else label="触发失败" tone="error" />
            <AppButton
              v-if="run.taskId"
              tone="text"
              @click="$emit('runtime', run.taskId, schedule.deviceName)"
            >
              运行详情
            </AppButton>
            <span v-else class="schedule-runs__reason">
              {{ run.triggerErrorMessage ?? '未创建任务' }}
            </span>
          </li>
        </ul>
        <EmptyState v-else description="暂无执行记录" />
      </section>

      <section>
        <h3>更多信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="Application ID">
            {{ schedule.applicationId }}
          </NDescriptionsItem>
          <NDescriptionsItem label="Skill ID">
            {{ schedule.skillId }}
          </NDescriptionsItem>
          <NDescriptionsItem label="创建时间">
            {{ schedule.createdAtDisplay }}
          </NDescriptionsItem>
          <NDescriptionsItem label="更新时间">
            {{ schedule.updatedAtDisplay }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>
    </div>

    <template #footer>
      <div v-if="schedule" class="schedule-detail-footer">
        <AppButton tone="danger" :loading="removing" @click="$emit('remove')">
          移除计划
        </AppButton>
        <span class="schedule-detail-footer__spacer" />
        <AppButton @click="$emit('edit')">编辑</AppButton>
        <AppButton :loading="statusChanging" @click="$emit('toggle')">
          {{ schedule.enabled ? '停用计划' : '启用计划' }}
        </AppButton>
        <AppButton @click="$emit('update:show', false)">关闭</AppButton>
      </div>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.schedule-detail-header,
.schedule-detail-footer,
.schedule-runs li {
  display: flex;
  align-items: center;
}

.schedule-detail-header {
  min-width: 0;
  flex: 1;
  justify-content: space-between;
  gap: var(--space-3);
}

.schedule-detail-header strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-detail {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.schedule-detail h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.schedule-runs {
  margin: 0;
  padding: 0;
  list-style: none;
}

.schedule-runs li {
  min-width: 0;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-subtle);
  gap: var(--space-3);
}

.schedule-runs__reason {
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-detail-footer {
  width: 100%;
  gap: var(--space-2);
}

.schedule-detail-footer__spacer {
  flex: 1;
}
</style>
