<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { computed } from 'vue'

import {
  type GenerationMode,
  type ProductMaterialGroup,
  type TemplateGroupOption,
} from '../model/types'
import { AppSelect, AppSwitch } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{
  product: ProductMaterialGroup
  templateGroupOptions: readonly TemplateGroupOption[]
  readOnly?: boolean
}>()

const emit = defineEmits<{
  'update:enabled': [value: boolean]
  'update:normalGenerationEnabled': [value: boolean]
  'update:styleReplicationEnabled': [value: boolean]
  'update:normalTemplateGroupIds': [value: string[]]
  'update:styleReplicationTemplateGroupIds': [value: string[]]
}>()

function templateOptions(mode: GenerationMode): SelectOption[] {
  return props.templateGroupOptions
    .filter((option) => option.mode === mode)
    .map((option) => ({
      label: option.label,
      value: option.id,
    }))
}

const normalTemplateOptions = computed(() =>
  templateOptions('NORMAL_GENERATION'),
)
const styleReplicationTemplateOptions = computed(() =>
  templateOptions('STYLE_REPLICATION'),
)

function templateGroupIds(value: AppOptionValue[]): string[] {
  return value.map(String)
}

function updateNormalTemplates(value: AppOptionValue[]): void {
  emit('update:normalTemplateGroupIds', templateGroupIds(value))
}

function updateStyleReplicationTemplates(value: AppOptionValue[]): void {
  emit('update:styleReplicationTemplateGroupIds', templateGroupIds(value))
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
          :disabled="readOnly"
          aria-label="产品启用"
          @update:model-value="$emit('update:enabled', $event)"
        />
      </label>
      <div class="product-material-settings__mode">
        <label class="product-material-settings__row">
          <span>普通生图</span>
          <AppSwitch
            :model-value="product.normalGenerationEnabled"
            :disabled="readOnly || !product.enabled"
            aria-label="普通生图"
            @update:model-value="
              $emit('update:normalGenerationEnabled', $event)
            "
          />
        </label>
        <label class="product-material-settings__field">
          <span>模板组</span>
          <AppSelect
            :model-value="product.normalTemplateGroupIds"
            :options="normalTemplateOptions"
            :disabled="
              readOnly || !product.enabled || !product.normalGenerationEnabled
            "
            multiple
            clearable
            filterable
            :max-tag-count="1"
            placeholder="未绑定"
            aria-label="普通生图模板组"
            @update:values="updateNormalTemplates"
          />
        </label>
      </div>
      <div class="product-material-settings__mode">
        <label class="product-material-settings__row">
          <span>风格复刻</span>
          <AppSwitch
            :model-value="product.styleReplicationEnabled"
            :disabled="readOnly || !product.enabled"
            aria-label="风格复刻"
            @update:model-value="
              $emit('update:styleReplicationEnabled', $event)
            "
          />
        </label>
        <label class="product-material-settings__field">
          <span>模板组</span>
          <AppSelect
            :model-value="product.styleReplicationTemplateGroupIds"
            :options="styleReplicationTemplateOptions"
            :disabled="
              readOnly || !product.enabled || !product.styleReplicationEnabled
            "
            multiple
            clearable
            filterable
            :max-tag-count="1"
            placeholder="未绑定"
            aria-label="风格复刻模板组"
            @update:values="updateStyleReplicationTemplates"
          />
        </label>
      </div>
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

.product-material-settings__mode {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
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
