<script setup lang="ts">
import { computed } from 'vue'

import { getPlatformDefinition, type PlatformCode } from '../model/registry'
import PlatformIcon from './PlatformIcon.vue'

const props = withDefaults(
  defineProps<{
    code: PlatformCode
    label?: boolean
    supportLabel?: string
  }>(),
  { label: true, supportLabel: undefined },
)

const meta = computed(() => getPlatformDefinition(props.code))
</script>

<template>
  <span v-if="meta" class="platform-display">
    <PlatformIcon :code="code" />
    <span v-if="label">{{ meta.label }}</span>
    <span v-if="supportLabel" class="platform-display__support">
      {{ supportLabel }}
    </span>
  </span>
</template>

<style scoped>
.platform-display {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.platform-display__support {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
