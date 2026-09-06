<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import { AiModuleShell } from '@/features/ai-workbench'
import GenerationRecordsRealPanel from '@/features/ai-workbench/generation-records/ui/GenerationRecordsRealPanel.vue'
import { isAiGenerationVisualMockEnabled } from '@/features/ai-workbench/generation/model/visual-mock-gate'

const visualMockEnabled = import.meta.env.DEV
  ? (() => {
      const route = useRoute()
      return computed(() =>
        isAiGenerationVisualMockEnabled(true, route.query.visualMock),
      )
    })()
  : null
const GenerationRecordsVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/generation-records/ui/GenerationRecordsVisualMock.vue'),
    )
  : null
</script>

<template>
  <AiModuleShell>
    <GenerationRecordsVisualMock
      v-if="visualMockEnabled && GenerationRecordsVisualMock"
    />
    <GenerationRecordsRealPanel v-else />
  </AiModuleShell>
</template>
