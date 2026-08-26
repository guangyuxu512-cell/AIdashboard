<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Empty as VanEmpty,
  Loading as VanLoading,
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
}>()

const emit = defineEmits<{ retry: [] }>()
const summary = computed(() =>
  summarizeDeviceCapabilities(props.capabilities ?? []),
)
</script>

<template>
  <section
    class="device-skill-summary mobile-section-surface"
    aria-labelledby="skill-summary-title"
  >
    <h2 id="skill-summary-title">能力</h2>

    <div v-if="initialLoading" class="device-skill-summary__state">
      <VanLoading>加载中</VanLoading>
    </div>
    <VanEmpty v-else-if="initialError" image="error" description="加载失败">
      <VanButton type="primary" @click="emit('retry')">重试</VanButton>
    </VanEmpty>
    <VanEmpty
      v-else-if="capabilities?.length === 0"
      description="暂无能力"
      data-testid="capability-empty"
    />
    <VanCellGroup v-else-if="capabilities" data-testid="capability-summary">
      <VanCell title="业务" :value="`${summary.business} 个`" />
      <VanCell title="内部" :value="`${summary.internal} 个`" />
    </VanCellGroup>
  </section>
</template>

<style scoped>
.device-skill-summary {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-3);
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

.device-skill-summary :deep(.van-cell-group) {
  border: 0;
  border-radius: 0;
}
</style>
