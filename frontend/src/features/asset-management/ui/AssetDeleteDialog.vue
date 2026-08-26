<script setup lang="ts">
import type { AssetListItemViewModel } from '@/entities/asset'
import AppDialog from '@/shared/ui/AppDialog.vue'

defineProps<{
  show: boolean
  asset: AssetListItemViewModel | null
  loading?: boolean
}>()
defineEmits<{
  'update:show': [value: boolean]
  confirm: []
}>()
</script>

<template>
  <AppDialog
    :show="show"
    title="删除图片"
    size="sm"
    positive-text="删除"
    :loading="loading"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm')"
  >
    确认删除“{{ asset?.filename }}”？已被任务引用的图片不会被删除。
  </AppDialog>
</template>
