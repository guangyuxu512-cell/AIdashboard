<script setup lang="ts">
import type { AutomationParameterPresetDto } from '@/entities/automation-application'
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  preset: AutomationParameterPresetDto | null
  submitting?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  confirm: []
}>()
</script>

<template>
  <AppDialog
    :show="show"
    title="删除配置"
    size="sm"
    positive-text="删除配置"
    :loading="submitting"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <div class="parameter-preset-delete-dialog">
      <p>确认删除配置“{{ preset?.name }}”？</p>
      <p>
        历史任务和已删除计划的参数快照会保留；仍被未删除的定时计划使用时，请先更换配置或删除计划。
      </p>
    </div>
  </AppDialog>
</template>

<style scoped>
.parameter-preset-delete-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  color: var(--text-secondary);
  line-height: var(--line-height-body);
}

.parameter-preset-delete-dialog p {
  margin: 0;
}

.parameter-preset-delete-dialog p:first-child {
  color: var(--text-primary);
}
</style>
