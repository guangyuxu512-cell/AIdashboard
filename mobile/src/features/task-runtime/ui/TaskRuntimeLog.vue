<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  Loading as VanLoading,
} from 'vant'
import { computed } from 'vue'

import type { TaskEventReadDto } from '@/entities/task'

import {
  RUNTIME_RETENTION_TEXT,
  getRuntimeRetentionState,
} from '../model/runtime-display'

const props = defineProps<{
  events: TaskEventReadDto[]
  initialized: boolean
  purgedAt: string | null
  loading: boolean
  loadingEarlier: boolean
  hasMoreBefore: boolean
  initialError: boolean
  backgroundError: boolean
  earlierError: boolean
  reachedMemoryLimit: boolean
}>()

const retentionText = computed(
  () =>
    RUNTIME_RETENTION_TEXT[
      getRuntimeRetentionState(props.purgedAt, props.events.length)
    ],
)

const emit = defineEmits<{
  retry: []
  retryLive: []
  loadEarlier: []
}>()

function eventTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}
</script>

<template>
  <section
    class="runtime-log mobile-section-surface"
    aria-labelledby="runtime-log-title"
  >
    <div class="runtime-log__heading">
      <h2 id="runtime-log-title">运行日志</h2>
      <span>{{ events.length }} 条</span>
    </div>

    <p v-if="initialized && retentionText" class="runtime-log__status">
      {{ retentionText }}
    </p>
    <p
      v-if="reachedMemoryLimit"
      class="runtime-log__status"
      data-testid="event-limit-notice"
    >
      仅显示最近 500 条日志
    </p>
    <div v-if="backgroundError" class="runtime-log__inline-error">
      <span>刷新失败</span>
      <VanButton data-testid="retry-runtime-sync" @click="emit('retryLive')">
        重试
      </VanButton>
    </div>
    <p v-if="earlierError" class="runtime-log__status">加载失败</p>

    <div v-if="loading && events.length === 0" class="runtime-log__state">
      <VanLoading>加载中</VanLoading>
    </div>
    <VanEmpty
      v-else-if="initialError && events.length === 0"
      image="error"
      description="加载失败"
    >
      <VanButton type="primary" @click="emit('retry')">重试</VanButton>
    </VanEmpty>
    <template v-else>
      <VanButton
        v-if="hasMoreBefore && !reachedMemoryLimit"
        block
        :loading="loadingEarlier"
        data-testid="load-earlier-events"
        @click="emit('loadEarlier')"
      >
        更早日志
      </VanButton>
      <ol
        v-if="events.length"
        class="runtime-log__items"
        data-testid="runtime-events"
      >
        <li v-for="event in events" :key="event.seq">
          <div class="runtime-log__meta">
            <span class="runtime-log__sequence">#{{ event.seq }}</span>
            <time :datetime="event.event_at">{{
              eventTime(event.event_at)
            }}</time>
          </div>
          <span class="runtime-log__message">{{ event.message }}</span>
        </li>
      </ol>
    </template>
  </section>
</template>

<style scoped>
.runtime-log {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
}

.runtime-log__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.runtime-log__heading h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.runtime-log__heading span,
.runtime-log__sequence,
.runtime-log time {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

.runtime-log__status {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.runtime-log__inline-error {
  display: flex;
  min-height: var(--touch-target-min);
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
}

.runtime-log__state {
  display: grid;
  min-height: var(--layout-inline-state-min-height);
  place-items: center;
}

.runtime-log__items {
  display: grid;
  gap: var(--layout-content-gap);
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.runtime-log__items li {
  display: grid;
  gap: var(--layout-content-gap);
  padding-bottom: var(--layout-content-gap);
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.runtime-log__meta {
  display: flex;
  min-width: 0;
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: space-between;
  font-family: var(--font-family-mono);
}

.runtime-log__message {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
