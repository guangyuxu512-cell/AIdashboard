<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import { AiManagementToolbar } from '@/features/ai-workbench'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'

import {
  GENERATION_WORK_MODE_META,
  type GenerationWorkMode,
} from '../model/types'
import { useAiGenerationRuntime } from '../model/useAiGenerationRuntime'
import BatchGenerationPanel from './BatchGenerationPanel.vue'
import InstantGenerationPanel from './InstantGenerationPanel.vue'

const { generationStore } = useAiGenerationRuntime()
const { workMode } = storeToRefs(generationStore)
const outputCompressionEnabled = ref(false)
const workModeOptions = [
  { label: GENERATION_WORK_MODE_META.INSTANT.label, key: 'INSTANT' },
  { label: GENERATION_WORK_MODE_META.BATCH.label, key: 'BATCH' },
]

function setWorkMode(value: string): void {
  generationStore.setWorkMode(value as GenerationWorkMode)
}
</script>

<template>
  <AiManagementToolbar label="生成工作方式">
    <span class="ai-generate__work-mode-label">工作方式</span>
    <ContextSwitchBar
      label="生成工作方式"
      appearance="bare"
      :active-key="workMode"
      :items="workModeOptions"
      @select="setWorkMode"
    />
  </AiManagementToolbar>
  <InstantGenerationPanel
    v-if="workMode === 'INSTANT'"
    v-model:output-compression-enabled="outputCompressionEnabled"
  />
  <BatchGenerationPanel
    v-else
    v-model:output-compression-enabled="outputCompressionEnabled"
  />
</template>

<style scoped>
.ai-generate__work-mode-label {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-medium);
}
</style>
