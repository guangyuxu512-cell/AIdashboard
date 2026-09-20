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
        已被历史任务或定时计划引用的配置不能删除；删除不会修改应用字段、店铺或既有任务快照。
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
