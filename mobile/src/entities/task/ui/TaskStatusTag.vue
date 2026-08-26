<script setup lang="ts">
import { Tag as VanTag } from 'vant'

import type { TaskStatusDto } from '../api/contracts'
import { TASK_STATUS_META } from '../model/status-meta'

defineProps<{ status: TaskStatusDto }>()
</script>

<template>
  <VanTag :type="TASK_STATUS_META[status].tagType" round>
    {{ TASK_STATUS_META[status].label }}
  </VanTag>
</template>
