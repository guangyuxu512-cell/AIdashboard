<script setup lang="ts">
import { Cell as VanCell, CellGroup as VanCellGroup } from 'vant'
import { computed } from 'vue'

import {
  summarizeDeviceCapabilities,
  type DeviceSkillCapabilityReadDto,
} from '@/entities/device'

const props = defineProps<{
  capabilities: DeviceSkillCapabilityReadDto[] | undefined
}>()

const summary = computed(() =>
  summarizeDeviceCapabilities(props.capabilities ?? []),
)
</script>

<template>
  <section class="device-skill-details" aria-label="技能能力技术信息">
    <h3>技能能力技术信息</h3>
    <p v-if="!capabilities" class="device-skill-details__empty">暂无信息</p>
    <VanCellGroup v-else data-testid="capability-technical-details">
      <VanCell title="能力总数" :value="`${summary.total} 个`" />
      <VanCell title="未分类能力" :value="`${summary.unclassified} 个`" />
    </VanCellGroup>
  </section>
</template>

<style scoped>
.device-skill-details {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.device-skill-details h3 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-skill-details__empty {
  color: var(--text-secondary);
}
</style>
