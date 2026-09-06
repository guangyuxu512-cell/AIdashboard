<script setup lang="ts">
import { useAiGenerationRuntime } from '../../generation/model/useAiGenerationRuntime'
import GenerationRecordsPanel from './GenerationRecordsPanel.vue'

useAiGenerationRuntime()
</script>

<template>
  <GenerationRecordsPanel />
</template>
