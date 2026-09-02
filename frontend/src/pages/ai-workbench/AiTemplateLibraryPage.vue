<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { Plus } from '@lucide/vue'
import { useRoute } from 'vue-router'

import {
  AiManagementLayout,
  AiManagementToolbar,
  AiModuleShell,
  AiWorkspaceEmptyState,
} from '@/features/ai-workbench'
import { isAiTemplatesVisualMockEnabled } from '@/features/ai-workbench/templates/model/visual-mock-gate'
import { GENERATION_MODE_META } from '@/features/ai-workbench/templates/model/types'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'

const route = useRoute()
const visualMockEnabled = computed(() =>
  isAiTemplatesVisualMockEnabled(import.meta.env.DEV, route.query.visualMock),
)
const AiTemplateLibraryVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/templates/ui/AiTemplateLibraryVisualMock.vue'),
    )
  : null

const normalModeOptions = [
  {
    value: 'NORMAL_GENERATION',
    label: GENERATION_MODE_META.NORMAL_GENERATION.label,
  },
  {
    value: 'STYLE_REPLICATION',
    label: GENERATION_MODE_META.STYLE_REPLICATION.label,
  },
]
</script>

<template>
  <AiModuleShell>
    <AiTemplateLibraryVisualMock
      v-if="visualMockEnabled && AiTemplateLibraryVisualMock"
    />
    <template v-else>
      <AiManagementToolbar label="模板库工具栏">
        <AppInput width="lg" placeholder="搜索模板" disabled />
        <template #actions>
          <AppSelect
            class="template-library-mode-select"
            model-value="NORMAL_GENERATION"
            :options="normalModeOptions"
            width="sm"
            aria-label="生成模式"
            disabled
          />
          <AppButton tone="primary" disabled>
            <Plus :size="16" />
            新建模板组
          </AppButton>
        </template>
      </AiManagementToolbar>

      <AiManagementLayout label="模板列表">
        <AiWorkspaceEmptyState title="暂无模板" />
      </AiManagementLayout>
    </template>
  </AiModuleShell>
</template>

<style scoped>
.template-library-mode-select {
  width: var(--field-width-sm);
  flex: 0 0 var(--field-width-sm);
}
</style>
