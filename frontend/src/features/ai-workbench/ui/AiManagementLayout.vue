<script setup lang="ts">
import PageSection from '@/shared/components/PageSection.vue'

defineProps<{
  label: string
}>()
</script>

<template>
  <PageSection class="ai-management-layout" :aria-label="label" fill>
    <slot />
  </PageSection>
</template>

<style scoped>
.ai-management-layout {
  min-width: 0;
  min-height: 0;
  flex: 1;
}
</style>
