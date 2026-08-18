<script setup lang="ts">
import AppButton from '@/shared/ui/AppButton.vue'
import AppDrawer from '@/shared/ui/AppDrawer.vue'
import type { OverlaySize } from '@/shared/ui/types'

withDefaults(
  defineProps<{ show: boolean; title: string; size?: OverlaySize; submitting?: boolean }>(),
  { size: 'md', submitting: false },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  submit: []
  cancel: []
}>()

function cancel(): void {
  emit('update:show', false)
  emit('cancel')
}
</script>

<template>
  <AppDrawer
    :show="show"
    :title="title"
    :size="size"
    @update:show="$emit('update:show', $event)"
  >
    <slot />
    <template #footer>
      <div class="form-drawer__footer">
        <AppButton @click="cancel">取消</AppButton>
        <AppButton tone="primary" :loading="submitting" @click="$emit('submit')">保存</AppButton>
      </div>
    </template>
  </AppDrawer>
</template>

<style scoped>
.form-drawer__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
</style>
