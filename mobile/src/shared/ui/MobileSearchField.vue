<script setup lang="ts">
import { MobileIcon } from '@/shared/icons'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: string
    placeholder?: string
    disabled?: boolean
    ariaLabel?: string
  }>(),
  {
    modelValue: '',
    placeholder: '搜索',
    disabled: false,
    ariaLabel: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  input: [value: string]
  change: [value: string]
}>()

function readValue(event: Event): string {
  return (event.target as HTMLInputElement).value
}

function handleInput(event: Event): void {
  const value = readValue(event)
  emit('update:modelValue', value)
  emit('input', value)
}

function handleChange(event: Event): void {
  emit('change', readValue(event))
}
</script>

<template>
  <label
    class="mobile-search-field"
    :class="{ 'mobile-search-field--disabled': disabled }"
    data-testid="mobile-search-field"
  >
    <MobileIcon class="mobile-search-field__icon" name="search" />
    <input
      v-bind="$attrs"
      type="search"
      :value="props.modelValue"
      :disabled="disabled"
      :placeholder="placeholder"
      :aria-label="ariaLabel || placeholder"
      autocomplete="off"
      @input="handleInput"
      @change="handleChange"
    />
  </label>
</template>

<style scoped>
.mobile-search-field {
  display: flex;
  width: 100%;
  min-width: 0;
  height: var(--visual-v2-search-height);
  align-items: center;
  padding: 0 var(--visual-v2-search-padding-x);
  color: var(--visual-v2-search-placeholder-color);
  background: var(--visual-v2-search-background);
  border: var(--visual-v2-search-border-width) solid
    var(--visual-v2-search-border-color);
  border-radius: var(--visual-v2-search-radius);
  box-shadow: var(--visual-v2-search-shadow);
}

.mobile-search-field:focus-within {
  border-color: var(--focus-ring-color);
  box-shadow: 0 0 0 var(--focus-ring-width) var(--color-primary-soft);
}

.mobile-search-field--disabled {
  color: var(--visual-v2-search-disabled-color);
}

.mobile-search-field__icon {
  width: var(--visual-v2-search-icon-size);
  height: var(--visual-v2-search-icon-size);
  flex: none;
  font-size: var(--visual-v2-search-icon-size);
}

.mobile-search-field input {
  width: 100%;
  min-width: 0;
  height: 100%;
  padding: 0 0 0 var(--visual-v2-search-icon-gap);
  color: var(--visual-v2-search-input-color);
  font-size: var(--typography-v2-search-size);
  font-weight: var(--typography-v2-search-weight);
  line-height: var(--typography-v2-search-line-height);
  appearance: none;
  background: transparent;
  border: 0;
  outline: 0;
}

.mobile-search-field input::placeholder {
  color: var(--visual-v2-search-placeholder-color);
  opacity: 1;
}

.mobile-search-field input:disabled {
  cursor: default;
  opacity: 1;
}

.mobile-search-field input::-webkit-search-cancel-button {
  appearance: none;
}
</style>
