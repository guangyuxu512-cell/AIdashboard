<script setup lang="ts">
import { Upload } from '@lucide/vue'

import {
  AiManagementLayout,
  AiManagementToolbar,
  AiModuleShell,
  AiWorkspaceEmptyState,
} from '@/features/ai-workbench'
import { AppButton, AppInput } from '@/shared/ui'
</script>

<template>
  <AiModuleShell>
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
  </AiModuleShell>
</template>
