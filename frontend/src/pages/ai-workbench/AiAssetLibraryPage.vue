<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import { AiModuleShell } from '@/features/ai-workbench'
import { isAiAssetsVisualMockEnabled } from '@/features/ai-workbench/assets/model/visual-mock-gate'
import AiAssetLibraryReal from '@/features/ai-workbench/assets/ui/AiAssetLibraryReal.vue'

const visualMockEnabled = import.meta.env.DEV
  ? (() => {
      const route = useRoute()
      return computed(() =>
        isAiAssetsVisualMockEnabled(true, route.query.visualMock),
      )
    })()
  : null
const AiAssetLibraryVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/assets/ui/AiAssetLibraryVisualMock.vue'),
    )
  : null
</script>

<template>
  <AiModuleShell>
    <AiAssetLibraryVisualMock
      v-if="visualMockEnabled && AiAssetLibraryVisualMock"
    />
    <AiAssetLibraryReal v-else />
  </AiModuleShell>
</template>
