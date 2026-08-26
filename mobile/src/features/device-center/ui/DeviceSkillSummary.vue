<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Empty as VanEmpty,
  Loading as VanLoading,
  NoticeBar as VanNoticeBar,
} from 'vant'
import { computed } from 'vue'

import {
  summarizeDeviceCapabilities,
  type DeviceSkillCapabilityReadDto,
} from '@/entities/device'

const props = defineProps<{
  capabilities: DeviceSkillCapabilityReadDto[] | undefined
  initialLoading: boolean
  initialError: boolean
  backgroundError: boolean
  errorMessage: string
}>()

const emit = defineEmits<{ retry: [] }>()
const summary = computed(() =>
  summarizeDeviceCapabilities(props.capabilities ?? []),
)
</script>

<template>
  <section class="device-skill-summary" aria-labelledby="skill-summary-title">
    <h2 id="skill-summary-title">技能能力摘要</h2>
    <div v-if="backgroundError" class="device-skill-summary__error">
      <VanNoticeBar
        class="mobile-notice-bar--warning"
        :text="`${errorMessage}，已保留上次技能能力快照`"
        wrapable
      />
      <VanButton block @click="emit('retry')">重新加载技能能力</VanButton>
    </div>

    <div v-if="initialLoading" class="device-skill-summary__state">
      <VanLoading>加载技能能力中</VanLoading>
    </div>
    <VanEmpty
      v-else-if="initialError"
      image="error"
      :description="errorMessage"
    >
      <VanButton type="primary" @click="emit('retry')">重新加载</VanButton>
    </VanEmpty>
    <VanEmpty
      v-else-if="capabilities?.length === 0"
      description="暂无技能能力记录"
      data-testid="capability-empty"
    />
    <VanCellGroup v-else-if="capabilities" data-testid="capability-summary">
      <VanCell title="业务能力" :value="`${summary.business} 个`" />
      <VanCell title="内部能力" :value="`${summary.internal} 个`" />
    </VanCellGroup>
  </section>
</template>

<style scoped>
.device-skill-summary {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.device-skill-summary h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-skill-summary__state {
  display: grid;
  min-height: var(--layout-inline-state-min-height);
  place-items: center;
}

.device-skill-summary__error {
  display: grid;
  gap: var(--space-2);
}
</style>
