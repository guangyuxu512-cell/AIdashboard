<script setup lang="ts">
import StatusTag from '@/shared/components/StatusTag.vue'

import type { TaskStatusDto } from '../api/contracts'
import { TASK_STATUS_META } from '../model/status-meta'

defineProps<{ status: TaskStatusDto }>()
</script>

<template>
  <StatusTag
    :label="TASK_STATUS_META[status].label"
    :tone="TASK_STATUS_META[status].tone"
  />
</template>
