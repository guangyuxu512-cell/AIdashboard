<script setup lang="ts">
import { Upload } from '@lucide/vue'
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import {
  AiManagementLayout,
  AiManagementToolbar,
  AiModuleShell,
  AiWorkspaceEmptyState,
} from '@/features/ai-workbench'
import { isAiAssetsVisualMockEnabled } from '@/features/ai-workbench/assets/model/visual-mock-gate'
import { AppButton, AppInput } from '@/shared/ui'

const route = useRoute()
const visualMockEnabled = computed(() =>
  isAiAssetsVisualMockEnabled(import.meta.env.DEV, route.query.visualMock),
)
const AiAssetLibraryVisualMock = import.meta.env.DEV
  ? defineAsyncComponent(
      () =>
        import('@/features/ai-workbench/assets/ui/AiAssetLibraryVisualMock.vue'),
    )
  : null
</script>

<template>
  <AiModuleShell>
    <AiAssetLibraryVisualMock
      v-if="visualMockEnabled && AiAssetLibraryVisualMock"
    />
    <template v-else>
      <AiManagementToolbar label="素材库工具栏">
        <AppInput width="lg" placeholder="搜索素材" disabled />
        <template #actions>
          <AppButton disabled>筛选</AppButton>
          <AppButton tone="primary" disabled>
            <Upload :size="16" />
            上传素材
          </AppButton>
        </template>
      </AiManagementToolbar>

      <AiManagementLayout label="素材列表">
        <AiWorkspaceEmptyState title="暂无素材" />
      </AiManagementLayout>
    </template>
  </AiModuleShell>
</template>
