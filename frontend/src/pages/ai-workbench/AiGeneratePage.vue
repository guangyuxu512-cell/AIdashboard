<script setup lang="ts">
import { storeToRefs } from 'pinia'

import { AiManagementToolbar, AiModuleShell } from '@/features/ai-workbench'
import {
  GENERATION_WORK_MODE_META,
  type GenerationWorkMode,
} from '@/features/ai-workbench/generation/model/types'
import { useAiGenerationRuntime } from '@/features/ai-workbench/generation/model/useAiGenerationRuntime'
import BatchGenerationPanel from '@/features/ai-workbench/generation/ui/BatchGenerationPanel.vue'
import InstantGenerationPanel from '@/features/ai-workbench/generation/ui/InstantGenerationPanel.vue'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'

const { generationStore } = useAiGenerationRuntime()
const { workMode } = storeToRefs(generationStore)

const workModeOptions = [
  { label: GENERATION_WORK_MODE_META.INSTANT.label, key: 'INSTANT' },
  { label: GENERATION_WORK_MODE_META.BATCH.label, key: 'BATCH' },
]

function setWorkMode(value: string): void {
  generationStore.setWorkMode(value as GenerationWorkMode)
}
</script>

<template>
  <AiModuleShell>
    <AiManagementToolbar label="生成工作方式">
      <span class="ai-generate-page__work-mode-label">工作方式</span>
      <ContextSwitchBar
        label="生成工作方式"
        appearance="bare"
        :active-key="workMode"
        :items="workModeOptions"
        @select="setWorkMode"
      />
    </AiManagementToolbar>
    <InstantGenerationPanel v-if="workMode === 'INSTANT'" />
    <BatchGenerationPanel v-else />
  </AiModuleShell>
</template>

<style scoped>
.ai-generate-page__work-mode-label {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-medium);
}
</style>
