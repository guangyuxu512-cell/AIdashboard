<script setup lang="ts">
import { Sparkles } from '@lucide/vue'

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
    <AiManagementToolbar label="模板库工具栏">
      <AppInput width="lg" placeholder="搜索模板" disabled />
      <template #actions>
        <AppButton disabled>分类</AppButton>
        <AppButton tone="primary" disabled>
          <Sparkles :size="16" />
          新建模板
        </AppButton>
      </template>
    </AiManagementToolbar>

    <AiManagementLayout label="模板列表">
      <AiWorkspaceEmptyState title="暂无模板" />
    </AiManagementLayout>
  </AiModuleShell>
</template>
