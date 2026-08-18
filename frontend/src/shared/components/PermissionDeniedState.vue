<script setup lang="ts">
import { NResult } from 'naive-ui'

withDefaults(defineProps<{ description?: string }>(), {
  description: '当前账号没有访问此内容的权限。',
})
</script>

<template>
  <NResult status="403" title="无访问权限" :description="description" class="state-panel">
    <template v-if="$slots.actions" #footer>
      <slot name="actions" />
    </template>
  </NResult>
</template>

<style scoped>
.state-panel {
  min-height: 180px;
  padding: var(--space-6);
}
</style>
