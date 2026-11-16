<script setup lang="ts">
import { AppSwitch } from '@/shared/ui'

defineProps<{
  modelValue: boolean
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<template>
  <label class="generation-output-compression">
    <span class="generation-output-compression__copy">
      <strong>生成后压缩</strong>
      <small>压缩至 1000 KB 以下</small>
    </span>
    <AppSwitch
      :model-value="modelValue"
      aria-label="生成后压缩至 1000 KB 以下"
      @update:model-value="$emit('update:modelValue', $event)"
    />
  </label>
</template>

<style scoped>
.generation-output-compression {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  min-width: 0;
}

.generation-output-compression__copy {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.generation-output-compression__copy strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}

.generation-output-compression__copy small {
  color: var(--text-muted);
  font-size: var(--font-size-caption);
}
</style>
