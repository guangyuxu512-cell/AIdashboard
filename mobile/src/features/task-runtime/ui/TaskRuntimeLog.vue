<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  Loading as VanLoading,
  NoticeBar as VanNoticeBar,
} from 'vant'

import type { TaskEventReadDto } from '@/entities/task'

import {
  RUNTIME_RETENTION_TEXT,
  getRuntimeRetentionState,
} from '../model/runtime-display'

defineProps<{
  events: TaskEventReadDto[]
  initialized: boolean
  purgedAt: string | null
  loading: boolean
  loadingEarlier: boolean
  hasMoreBefore: boolean
  initialError: string | null
  backgroundError: string | null
  earlierError: string | null
  reachedMemoryLimit: boolean
}>()

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
  <section class="runtime-log" aria-labelledby="runtime-log-title">
    <div class="runtime-log__heading">
      <h2 id="runtime-log-title">运行日志</h2>
      <span>{{ events.length }} 条</span>
    </div>

    <VanNoticeBar
      v-if="initialized"
      :text="
        RUNTIME_RETENTION_TEXT[
          getRuntimeRetentionState(purgedAt, events.length)
        ]
      "
      wrapable
    />
    <VanNoticeBar
      v-if="reachedMemoryLimit"
      class="mobile-notice-bar--warning"
      text="为控制内存，页面最多保留 500 条日志；较早日志可能未展示。"
      wrapable
      data-testid="event-limit-notice"
    />
    <VanNoticeBar
      v-if="backgroundError"
      class="mobile-notice-bar--warning"
      :text="`${backgroundError}，已保留现有日志`"
      wrapable
    />
    <VanButton
      v-if="backgroundError"
      block
      data-testid="retry-runtime-sync"
      @click="emit('retryLive')"
    >
      重试同步
    </VanButton>
    <VanNoticeBar
      v-if="earlierError"
      class="mobile-notice-bar--warning"
      :text="earlierError"
      wrapable
    />

    <div v-if="loading && events.length === 0" class="runtime-log__state">
      <VanLoading>加载日志中</VanLoading>
    </div>
    <VanEmpty
      v-else-if="initialError && events.length === 0"
      image="error"
      :description="initialError"
    >
      <VanButton type="primary" @click="emit('retry')">重新加载</VanButton>
    </VanEmpty>
    <template v-else>
      <VanButton
        v-if="hasMoreBefore && !reachedMemoryLimit"
        block
        :loading="loadingEarlier"
        data-testid="load-earlier-events"
        @click="emit('loadEarlier')"
      >
        加载更早日志
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
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
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

.runtime-log__state {
  display: grid;
  min-height: var(--layout-inline-state-min-height);
  place-items: center;
}

.runtime-log__items {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.runtime-log__items li {
  display: grid;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.runtime-log__meta {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
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
