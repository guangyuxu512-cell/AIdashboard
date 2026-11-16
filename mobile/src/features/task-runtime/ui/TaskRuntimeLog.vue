<script setup lang="ts">
import { Button as VanButton, Loading as VanLoading } from 'vant'
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
    class="runtime-log"
    aria-labelledby="runtime-log-title"
    data-testid="runtime-log"
  >
    <div class="runtime-log__heading">
      <h2 id="runtime-log-title">运行日志</h2>
      <span>{{ events.length }} 条</span>
    </div>

    <div
      class="runtime-log__scroll mobile-scroll-container"
      data-testid="runtime-log-scroll"
    >
      <p
        v-if="initialized && events.length > 0 && retentionText"
        class="runtime-log__status"
      >
        {{ retentionText }}
      </p>
      <p
        v-if="reachedMemoryLimit"
        class="runtime-log__status"
        data-testid="event-limit-notice"
      >
        部分日志未显示
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
      <div
        v-else-if="initialError && events.length === 0"
        class="runtime-log__state runtime-log__state--error"
        data-testid="runtime-log-error"
      >
        <span>加载失败</span>
        <VanButton type="primary" @click="emit('retry')">重试</VanButton>
      </div>
      <p
        v-else-if="initialized && events.length === 0"
        class="runtime-log__empty"
        data-testid="runtime-log-empty"
      >
        {{ retentionText || '暂无运行日志' }}
      </p>
      <template v-else-if="events.length > 0">
        <VanButton
          v-if="hasMoreBefore && !reachedMemoryLimit"
          block
          :loading="loadingEarlier"
          data-testid="load-earlier-events"
          @click="emit('loadEarlier')"
        >
          更早日志
        </VanButton>
        <ol class="runtime-log__items" data-testid="runtime-events">
          <li
            v-for="event in events"
            :key="event.seq"
            class="runtime-log__item"
            :class="`runtime-log__item--${event.event_type}`"
          >
            <span class="runtime-log__track" aria-hidden="true">
              <i />
            </span>
            <div class="runtime-log__event">
              <span class="runtime-log__message">{{ event.message }}</span>
              <time :datetime="event.event_at">{{
                eventTime(event.event_at)
              }}</time>
            </div>
          </li>
        </ol>
      </template>
    </div>
  </section>
</template>

<style scoped>
.runtime-log {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-detail-surface-background);
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-surface-border-color);
  border-radius: var(--visual-v2-business-card-radius);
  box-shadow: var(--visual-v2-detail-surface-shadow);
}

.runtime-log__heading {
  display: flex;
  min-height: var(--touch-target-min);
  flex: none;
  padding-inline: var(--visual-v2-business-card-padding-left)
    var(--visual-v2-business-card-padding-right);
  align-items: center;
  justify-content: space-between;
  border-bottom: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-divider-color);
}

.runtime-log__heading h2 {
  font-size: var(--typography-v2-detail-section-title-size);
  font-weight: var(--typography-v2-detail-section-title-weight);
  line-height: var(--typography-v2-detail-section-title-line-height);
}

.runtime-log__heading span,
.runtime-log time {
  color: var(--visual-v2-detail-meta-color);
  font-size: var(--typography-v2-meta-size);
  font-weight: var(--typography-v2-meta-weight);
  line-height: var(--typography-v2-meta-line-height);
}

.runtime-log__scroll {
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  padding: 0 var(--visual-v2-business-card-padding-right)
    var(--visual-v2-business-card-padding-bottom)
    var(--visual-v2-business-card-padding-left);
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}

.runtime-log__status {
  padding-block: var(--space-2);
  color: var(--visual-v2-detail-meta-color);
  font-size: var(--typography-v2-meta-size);
  line-height: var(--typography-v2-detail-hero-meta-line-height);
}

.runtime-log__inline-error {
  display: flex;
  min-height: var(--touch-target-min);
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
  color: var(--visual-v2-detail-meta-color);
  font-size: var(--typography-v2-meta-size);
}

.runtime-log__state {
  display: flex;
  min-height: 100%;
  gap: var(--space-3);
  align-items: center;
  justify-content: center;
}

.runtime-log__state--error {
  flex-direction: column;
  color: var(--visual-v2-detail-meta-color);
}

.runtime-log__empty {
  display: grid;
  min-height: 100%;
  color: var(--visual-v2-detail-meta-color);
  font-size: var(--typography-v2-meta-size);
  line-height: var(--typography-v2-detail-hero-meta-line-height);
  text-align: center;
  place-items: center;
}

.runtime-log__items {
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.runtime-log__item {
  position: relative;
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding-block: var(--space-3);
  grid-template-columns: var(--space-4) minmax(0, 1fr);
}

.runtime-log__item:not(:last-child)::before {
  position: absolute;
  top: calc(var(--space-3) + var(--visual-v2-business-card-status-dot-size));
  bottom: calc(var(--space-3) * -1);
  left: calc(
    (var(--space-4) - var(--visual-v2-business-card-border-width)) / 2
  );
  width: var(--visual-v2-business-card-border-width);
  content: '';
  background: var(--visual-v2-detail-divider-color);
}

.runtime-log__track {
  position: relative;
  z-index: 1;
  display: grid;
  padding-top: var(--space-1);
  justify-content: center;
}

.runtime-log__track i {
  width: var(--visual-v2-business-card-status-dot-size);
  height: var(--visual-v2-business-card-status-dot-size);
  background: var(--visual-v2-detail-meta-color);
  border-radius: var(--radius-round);
}

.runtime-log__item--progress .runtime-log__track i,
.runtime-log__item--status .runtime-log__track i {
  background: var(--status-info);
}

.runtime-log__item--completed .runtime-log__track i {
  background: var(--status-success);
}

.runtime-log__item--failed .runtime-log__track i {
  background: var(--status-danger);
}

.runtime-log__event {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.runtime-log__message {
  min-width: 0;
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-regular);
  line-height: var(--line-height-body);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
