<script setup lang="ts">
import {
  Button as VanButton,
  NavBar as VanNavBar,
  Popup as VanPopup,
} from 'vant'
import { computed, ref, watch } from 'vue'

import { MobileIcon } from '@/shared/icons'

import {
  createTaskPresetDateRange,
  formatTaskDateInput,
  parseTaskDateInput,
  TASK_DATE_PRESET_OPTIONS,
  type TaskDatePreset,
  type TaskFilterDraft,
} from '../model/task-filter'

const props = defineProps<{
  modelValue: boolean
  filters: TaskFilterDraft
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  apply: [filters: TaskFilterDraft]
}>()

const selectedPreset = ref<TaskDatePreset>('last-7-days')
const dateInput = ref(formatTaskDateInput(new Date()))
const customDate = computed(() => parseTaskDateInput(dateInput.value))
const maxDate = formatTaskDateInput(new Date())

watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) return
    selectedPreset.value = props.filters.datePreset
    dateInput.value = formatTaskDateInput(
      props.filters.datePreset === 'custom'
        ? props.filters.dateRange[0]
        : new Date(),
    )
  },
  { immediate: true },
)

function applyPreset(preset: Exclude<TaskDatePreset, 'custom'>): void {
  const range = preset === 'all-time' ? null : createTaskPresetDateRange(preset)
  emit('apply', {
    ...props.filters,
    datePreset: preset,
    dateRange: range
      ? [range.start, range.endInclusive]
      : props.filters.dateRange,
  })
  emit('update:modelValue', false)
}

function applyCustomDate(): void {
  if (!customDate.value) return
  emit('apply', {
    ...props.filters,
    datePreset: 'custom',
    dateRange: [customDate.value, customDate.value],
  })
  emit('update:modelValue', false)
}
</script>

<template>
  <VanPopup
    :show="modelValue"
    position="bottom"
    round
    class="task-filter-sheet"
    data-testid="task-date-filter-sheet"
    @update:show="emit('update:modelValue', $event)"
  >
    <VanNavBar title="运行日期" />

    <div class="task-filter-sheet__body">
      <div class="task-filter-sheet__presets" aria-label="运行日期快捷筛选">
        <VanButton
          v-for="option in TASK_DATE_PRESET_OPTIONS"
          :key="option.value"
          class="task-filter-sheet__preset"
          :class="{
            'task-filter-sheet__preset--selected':
              selectedPreset === option.value,
          }"
          :aria-pressed="selectedPreset === option.value"
          :data-testid="`task-date-preset-${option.value}`"
          @click="applyPreset(option.value)"
        >
          {{ option.text }}
        </VanButton>
      </div>

      <label class="task-filter-sheet__date-field">
        <span>指定日期</span>
        <span class="task-filter-sheet__date-control">
          <MobileIcon name="calendar" />
          <input
            v-model="dateInput"
            type="date"
            :max="maxDate"
            aria-label="指定运行日期"
            data-testid="task-custom-date"
          />
        </span>
      </label>

      <VanButton
        block
        type="primary"
        :disabled="!customDate"
        data-testid="apply-task-custom-date"
        @click="applyCustomDate"
      >
        应用
      </VanButton>
    </div>
  </VanPopup>
</template>

<style scoped>
.task-filter-sheet {
  padding-right: var(--safe-area-right);
  padding-bottom: calc(var(--space-4) + var(--safe-area-bottom));
  padding-left: var(--safe-area-left);
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-detail-sheet-background);
}

.task-filter-sheet__body {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-3) var(--visual-v2-page-padding-x) var(--space-4);
}

.task-filter-sheet__presets {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.task-filter-sheet__preset {
  min-height: var(--touch-target-min);
  color: var(--text-secondary);
  background: var(--visual-v2-detail-weak-background);
  border-color: var(--visual-v2-detail-weak-border-color);
  border-radius: var(--radius-control);
}

.task-filter-sheet__preset--selected {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.task-filter-sheet__date-field {
  display: flex;
  min-width: 0;
  min-height: var(--touch-target-min);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  color: var(--text-secondary);
}

.task-filter-sheet__date-control {
  display: flex;
  min-width: 0;
  min-height: var(--touch-target-min);
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  color: var(--text-secondary);
  background: var(--visual-v2-detail-weak-background);
  border: var(--border-width) solid var(--visual-v2-detail-weak-border-color);
  border-radius: var(--radius-control);
}

.task-filter-sheet__date-control .mobile-icon {
  flex: none;
}

.task-filter-sheet__date-control input {
  width: 9rem;
  min-width: 0;
  height: var(--touch-target-min);
  padding: 0;
  color: var(--visual-v2-page-text-primary);
  color-scheme: inherit;
  background: transparent;
  border: 0;
  outline: 0;
}
</style>
