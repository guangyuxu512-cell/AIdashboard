<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import { AiModuleShell } from '@/features/ai-workbench'
import { isAiTemplatesVisualMockEnabled } from '@/features/ai-workbench/templates/model/visual-mock-gate'
import AiTemplateLibraryReal from '@/features/ai-workbench/templates/ui/AiTemplateLibraryReal.vue'

const visualMockEnabled = import.meta.env.DEV
  ? (() => {
      const route = useRoute()
      return computed(() =>
        isAiTemplatesVisualMockEnabled(true, route.query.visualMock),
      )
    })()
  : null
const AiTemplateLibraryVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/templates/ui/AiTemplateLibraryVisualMock.vue'),
    )
  : null
</script>

<template>
  <AiModuleShell>
    <AiTemplateLibraryVisualMock
      v-if="visualMockEnabled && AiTemplateLibraryVisualMock"
    />
    <AiTemplateLibraryReal v-else />
  </AiModuleShell>
</template>
