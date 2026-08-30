<script setup lang="ts">
import { computed } from 'vue'
import type { SelectOption } from 'naive-ui'

import {
  TEMPLATE_GROUP_OPTIONS,
  UNBOUND_TEMPLATE_GROUP_VALUE,
  type ProductMaterialGroup,
} from '../model/types'
import { AppSelect, AppSwitch } from '@/shared/ui'

const props = defineProps<{
  product: ProductMaterialGroup
}>()

const emit = defineEmits<{
  'update:enabled': [value: boolean]
  'update:normalGenerationEnabled': [value: boolean]
  'update:styleReplicationEnabled': [value: boolean]
  'update:defaultTemplateGroupId': [value: string | null]
}>()

const templateOptions: SelectOption[] = [
  { label: '未绑定', value: UNBOUND_TEMPLATE_GROUP_VALUE },
  ...TEMPLATE_GROUP_OPTIONS.map((option) => ({
    label: option.label,
    value: option.id,
  })),
]

const templateValue = computed(
  () => props.product.defaultTemplateGroupId ?? UNBOUND_TEMPLATE_GROUP_VALUE,
)

function updateTemplate(value: string | number | null): void {
  emit(
    'update:defaultTemplateGroupId',
    value === UNBOUND_TEMPLATE_GROUP_VALUE || value === null
      ? null
      : String(value),
  )
}
</script>

<template>
  <section class="product-material-settings" aria-label="产品设置">
    <strong class="product-material-settings__title">产品设置</strong>
    <div class="product-material-settings__controls">
      <label class="product-material-settings__row">
        <span>启用</span>
        <AppSwitch
          :model-value="product.enabled"
          aria-label="产品启用"
          @update:model-value="$emit('update:enabled', $event)"
        />
      </label>
      <label class="product-material-settings__row">
        <span>普通生图</span>
        <AppSwitch
          :model-value="product.normalGenerationEnabled"
          :disabled="!product.enabled"
          aria-label="普通生图"
          @update:model-value="$emit('update:normalGenerationEnabled', $event)"
        />
      </label>
      <label class="product-material-settings__row">
        <span>风格复刻</span>
        <AppSwitch
          :model-value="product.styleReplicationEnabled"
          :disabled="!product.enabled"
          aria-label="风格复刻"
          @update:model-value="$emit('update:styleReplicationEnabled', $event)"
        />
      </label>
      <label class="product-material-settings__field">
        <span>默认模板组</span>
        <AppSelect
          :model-value="templateValue"
          :options="templateOptions"
          aria-label="默认模板组"
          @update:model-value="updateTemplate"
        />
      </label>
    </div>
  </section>
</template>

<style scoped>
.product-material-settings {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
}

.product-material-settings__title {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.product-material-settings__controls {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.product-material-settings__row,
.product-material-settings__field {
  display: flex;
  min-width: 0;
  gap: var(--space-3);
}

.product-material-settings__row {
  min-height: var(--control-height-large);
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.product-material-settings__field {
  flex-direction: column;
}

.product-material-settings__row > span,
.product-material-settings__field > span {
  color: var(--text-secondary);
  font-size: var(--font-size-body);
}
</style>
