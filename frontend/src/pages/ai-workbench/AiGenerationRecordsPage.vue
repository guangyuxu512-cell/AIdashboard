<script setup lang="ts">
import { AiModuleShell } from '@/features/ai-workbench'
import GenerationRecordsPanel from '@/features/ai-workbench/generation-records/ui/GenerationRecordsPanel.vue'
import { useAiGenerationRuntime } from '@/features/ai-workbench/generation/model/useAiGenerationRuntime'

useAiGenerationRuntime()
</script>

<template>
  <AiModuleShell>
    <GenerationRecordsPanel />
  </AiModuleShell>
</template>
