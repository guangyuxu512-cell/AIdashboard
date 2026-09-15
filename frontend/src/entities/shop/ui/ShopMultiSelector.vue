<script setup lang="ts">
import { computed, ref } from 'vue'

import { AppCheckbox, AppInput } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import type { ShopSelectOption } from '../model/types'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    options: ShopSelectOption[]
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    loading: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const keywordDraft = ref('')
const keyword = ref('')
const autoSearch = useAutoSearch(() => {
  keyword.value = keywordDraft.value
})
const visibleOptions = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLocaleLowerCase()
  const available = props.options.filter(
    (option) =>
      !normalizedKeyword ||
      option.label.toLocaleLowerCase().includes(normalizedKeyword),
  )
  const knownIds = new Set(props.options.map((option) => option.value))
  const retained = props.modelValue
    .filter((shopId) => !knownIds.has(shopId))
    .map((shopId) => ({
      label: `已保存店铺 · ${shopId}`,
      value: shopId,
      disabled: false,
    }))
  return [...retained, ...available]
})
const selectableIds = computed(() =>
  props.options
    .filter((option) => !option.disabled)
    .map((option) => option.value),
)
const allSelected = computed(
  () =>
    selectableIds.value.length > 0 &&
    selectableIds.value.every((shopId) => props.modelValue.includes(shopId)),
)

function toggleAll(checked: boolean): void {
  const retained = props.modelValue.filter(
    (shopId) => !selectableIds.value.includes(shopId),
  )
  emit(
    'update:modelValue',
    checked ? [...retained, ...selectableIds.value] : [],
  )
}

function toggleShop(shopId: string, checked: boolean): void {
  emit(
    'update:modelValue',
    checked
      ? [...props.modelValue, shopId]
      : props.modelValue.filter((value) => value !== shopId),
  )
}
</script>

<template>
  <div class="shop-multi-selector">
    <div class="shop-multi-selector__summary">
      <AppCheckbox
        :model-value="allSelected"
        :disabled="disabled || loading || !selectableIds.length"
        @update:model-value="toggleAll"
      >
        全选
      </AppCheckbox>
      <span>已选择 {{ modelValue.length }} 个店铺</span>
    </div>
    <AppInput
      v-model="keywordDraft"
      clearable
      :disabled="disabled"
      :loading="loading"
      placeholder="搜索店铺"
      @update:model-value="autoSearch.onInput"
      @compositionstart="autoSearch.onCompositionStart"
      @compositionend="autoSearch.onCompositionEnd(keywordDraft)"
      @keyup.enter="autoSearch.onEnter($event)"
    />
    <div class="shop-multi-selector__list">
      <AppCheckbox
        v-for="option in visibleOptions"
        :key="option.value"
        :model-value="modelValue.includes(option.value)"
        :disabled="disabled || option.disabled"
        @update:model-value="toggleShop(option.value, $event)"
      >
        {{ option.label }}
      </AppCheckbox>
      <span v-if="!loading && !visibleOptions.length" class="shop-multi-selector__empty">
        当前设备暂无可用的绑定店铺
      </span>
    </div>
  </div>
</template>

<style scoped>
.shop-multi-selector {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.shop-multi-selector__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.shop-multi-selector__list {
  display: flex;
  max-height: 220px;
  min-height: 72px;
  overflow-y: auto;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

.shop-multi-selector__empty {
  margin: auto;
  color: var(--text-tertiary);
}
</style>
