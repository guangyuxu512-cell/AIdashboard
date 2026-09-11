<script setup lang="ts">
import { Loading as VanLoading, PullRefresh as VanPullRefresh } from 'vant'
import { computed } from 'vue'

import { useMobilePullRefresh } from './mobile-pull-refresh'

const props = withDefaults(
  defineProps<{
    refresh: () => Promise<boolean>
    disabled?: boolean
  }>(),
  {
    disabled: false,
  },
)

const pullRefresh = useMobilePullRefresh(() => props.refresh())
const feedbackText = computed(() =>
  pullRefresh.feedback.value === 'error' ? '刷新失败' : '刷新完成',
)
</script>

<template>
  <VanPullRefresh
    class="mobile-pull-refresh"
    data-testid="mobile-pull-refresh"
    :disabled="disabled"
    :model-value="pullRefresh.refreshing.value"
    :animation-duration="pullRefresh.reboundDuration.value"
    :success-duration="pullRefresh.feedbackDuration.value"
    pulling-text="下拉刷新"
    loosing-text="松开刷新"
    loading-text="正在刷新"
    @change="pullRefresh.handleChange"
    @refresh="pullRefresh.runRefresh"
  >
    <template #pulling>
      <span data-testid="mobile-pull-refresh-pulling">下拉刷新</span>
    </template>
    <template #loosing>
      <span data-testid="mobile-pull-refresh-loosing">松开刷新</span>
    </template>
    <template #loading>
      <VanLoading size="16px">正在刷新</VanLoading>
    </template>
    <template #success>
      <span
        class="mobile-pull-refresh__feedback"
        :class="{
          'mobile-pull-refresh__feedback--error':
            pullRefresh.feedback.value === 'error',
        }"
        data-testid="mobile-pull-refresh-feedback"
        aria-live="polite"
        role="status"
      >
        {{ feedbackText }}
      </span>
    </template>

    <slot />
  </VanPullRefresh>
</template>

<style scoped>
.mobile-pull-refresh {
  min-height: 100%;
}

.mobile-pull-refresh :deep(.van-pull-refresh__head) {
  display: grid;
  place-items: center;
}

.mobile-pull-refresh__feedback {
  color: var(--status-success);
  font-size: var(--font-size-secondary);
  line-height: var(--line-height-secondary);
}

.mobile-pull-refresh__feedback--error {
  color: var(--status-danger);
}
</style>
