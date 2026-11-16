<script setup lang="ts">
import { Popup as VanPopup } from 'vant'

import type { ThemeMode } from '@/app/stores/theme'
import { MobileIcon } from '@/shared/icons'

defineProps<{
  show: boolean
  mode: ThemeMode
}>()

const emit = defineEmits<{
  'update:show': [show: boolean]
  select: [mode: ThemeMode]
}>()

const options = [
  { value: 'light', label: '浅色主题' },
  { value: 'dark', label: '深色主题' },
  { value: 'system', label: '跟随系统' },
] as const satisfies ReadonlyArray<{ value: ThemeMode; label: string }>
</script>

<template>
  <VanPopup
    class="mobile-theme-settings-sheet"
    :show="show"
    position="bottom"
    round
    :safe-area-inset-bottom="false"
    @update:show="emit('update:show', $event)"
  >
    <div class="mobile-theme-settings-sheet__handle" aria-hidden="true" />
    <section aria-labelledby="mobile-theme-settings-title">
      <h2 id="mobile-theme-settings-title">主题</h2>
      <div class="mobile-theme-settings-sheet__options">
        <button
          v-for="option in options"
          :key="option.value"
          type="button"
          class="mobile-theme-settings-sheet__option mobile-pressable"
          :class="{
            'mobile-theme-settings-sheet__option--selected':
              mode === option.value,
          }"
          :aria-pressed="mode === option.value"
          @click="emit('select', option.value)"
        >
          <span>{{ option.label }}</span>
          <MobileIcon v-if="mode === option.value" name="success" />
        </button>
      </div>
    </section>
  </VanPopup>
</template>

<style scoped>
.mobile-theme-settings-sheet {
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right))
    max(var(--space-5), var(--safe-area-bottom))
    max(var(--layout-page-padding-x), var(--safe-area-left));
  color: var(--text-primary);
  background: var(--bg-surface-raised);
}

.mobile-theme-settings-sheet__handle {
  width: var(--space-8);
  height: var(--space-1);
  margin: 0 auto var(--space-3);
  background: var(--border-strong);
  border-radius: var(--radius-round);
}

.mobile-theme-settings-sheet h2 {
  font-size: var(--font-size-title);
  line-height: var(--line-height-title);
}

.mobile-theme-settings-sheet__options {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.mobile-theme-settings-sheet__option {
  display: flex;
  width: 100%;
  min-height: var(--touch-target-min);
  padding: 0 var(--space-3);
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
  background: var(--bg-subtle);
  border: var(--border-width) solid transparent;
  border-radius: var(--radius-control);
  box-shadow: var(--appearance-border-control);
}

.mobile-theme-settings-sheet__option--selected {
  color: var(--text-selected);
  background: var(--bg-selected);
}

.mobile-theme-settings-sheet__option .mobile-icon {
  width: var(--icon-size-small);
  height: var(--icon-size-small);
  font-size: var(--icon-size-small);
}
</style>
