<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import { AiModuleShell } from '@/features/ai-workbench'
import { isAiGenerationVisualMockEnabled } from '@/features/ai-workbench/generation/model/visual-mock-gate'
import AiGenerationReal from '@/features/ai-workbench/generation/ui/AiGenerationReal.vue'

const visualMockEnabled = import.meta.env.DEV
  ? (() => {
      const route = useRoute()
      return computed(() =>
        isAiGenerationVisualMockEnabled(true, route.query.visualMock),
      )
    })()
  : null
const AiGenerationVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/generation/ui/AiGenerationVisualMock.vue'),
    )
  : null
</script>

<template>
  <AiModuleShell>
    <AiGenerationVisualMock
      v-if="visualMockEnabled && AiGenerationVisualMock"
    />
    <AiGenerationReal v-else />
  </AiModuleShell>
</template>
