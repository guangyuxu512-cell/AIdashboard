<script setup lang="ts">
import { NavBar as VanNavBar } from 'vant'

defineProps<{
  title: string
}>()

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <div class="mobile-detail-header" data-testid="mobile-detail-header">
    <VanNavBar
      :title="title"
      left-arrow
      :border="false"
      @click-left="emit('back')"
    />
  </div>
</template>

<style scoped>
.mobile-detail-header {
  padding-right: max(
    0px,
    calc(var(--safe-area-right) - var(--layout-page-padding-x))
  );
  padding-left: max(
    0px,
    calc(var(--safe-area-left) - var(--layout-page-padding-x))
  );
  background: var(--bg-surface);
  border-bottom: var(--border-width) solid var(--border-subtle);
}
</style>
