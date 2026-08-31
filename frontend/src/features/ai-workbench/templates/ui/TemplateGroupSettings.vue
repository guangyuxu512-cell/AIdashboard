<script setup lang="ts">
import { computed } from 'vue'

import { GENERATION_MODE_META, type TemplateGroup } from '../model/types'
import { AppSwitch } from '@/shared/ui'

const props = defineProps<{
  group: TemplateGroup
}>()

defineEmits<{
  'update:enabled': [value: boolean]
}>()

const modeLabel = computed(() => GENERATION_MODE_META[props.group.mode].label)
</script>

<template>
  <section class="template-group-settings" aria-label="模板组设置">
    <strong class="template-group-settings__title">模板组设置</strong>
    <div class="template-group-settings__fields">
      <div class="template-group-settings__field">
        <span>名称</span>
        <strong :title="group.name">{{ group.name }}</strong>
      </div>
      <div class="template-group-settings__field">
        <span>生成模式</span>
        <strong>{{ modeLabel }}</strong>
      </div>
      <label class="template-group-settings__field">
        <span>启用</span>
        <AppSwitch
          :model-value="group.enabled"
          aria-label="模板组启用"
          @update:model-value="$emit('update:enabled', $event)"
        />
      </label>
      <div class="template-group-settings__field">
        <span>模板数量</span>
        <strong>{{ group.templates.length }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.template-group-settings {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
}

.template-group-settings__title {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.template-group-settings__fields {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.template-group-settings__field {
  display: flex;
  min-width: 0;
  min-height: var(--control-height-large);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.template-group-settings__field > span {
  flex: 0 0 auto;
  color: var(--text-secondary);
}

.template-group-settings__field > strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
