<script setup lang="ts">
import type { ScheduleDetailViewModel } from '@/entities/schedule'
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  schedule: ScheduleDetailViewModel | null
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
    title="确认移除定时计划"
    size="sm"
    positive-text="确认移除"
    :loading="submitting"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    <p>
      移除计划“<strong>{{ schedule?.name }}</strong
      >”后将不再产生未来任务，已有任务和执行历史仍会保留。
    </p>
  </AppDialog>
</template>
