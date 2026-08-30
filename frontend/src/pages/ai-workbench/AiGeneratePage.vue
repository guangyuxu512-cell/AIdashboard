<script setup lang="ts">
import {
  AiModuleShell,
  AiWorkbenchLayout,
  AiWorkspaceEmptyState,
} from '@/features/ai-workbench'
import { AppButton, AppInput, AppRadio } from '@/shared/ui'

const generationModeOptions = [
  { label: '智能生成', value: 'smart' },
  { label: '风格参考', value: 'reference' },
]

const outputTypeOptions = [
  { label: '主图', value: 'main-image' },
  { label: '主图 + 详情', value: 'main-and-detail' },
]
</script>

<template>
  <AiModuleShell>
    <AiWorkbenchLayout>
      <template #operation>
        <div class="ai-generate-page__operation-stack">
          <section
            class="ai-generate-page__field"
            aria-labelledby="ai-material-label"
          >
            <strong id="ai-material-label">素材</strong>
            <AppButton block disabled>选择素材</AppButton>
          </section>

          <section
            class="ai-generate-page__field"
            aria-labelledby="ai-mode-label"
          >
            <strong id="ai-mode-label">生成模式</strong>
            <AppRadio
              model-value="smart"
              :options="generationModeOptions"
              disabled
            />
          </section>

          <section
            class="ai-generate-page__field"
            aria-labelledby="ai-output-label"
          >
            <strong id="ai-output-label">输出类型</strong>
            <AppRadio
              model-value="main-image"
              :options="outputTypeOptions"
              disabled
            />
          </section>

          <section
            class="ai-generate-page__field"
            aria-labelledby="ai-prompt-label"
          >
            <strong id="ai-prompt-label">提示词 / 模板</strong>
            <AppInput
              type="textarea"
              placeholder="请输入提示词或选择模板"
              disabled
            />
          </section>

          <div class="ai-generate-page__actions" aria-label="生成操作">
            <AppButton block tone="primary" disabled>开始生成</AppButton>
          </div>
        </div>
      </template>

      <template #workspace>
        <AiWorkspaceEmptyState title="暂无生成结果" />
      </template>
    </AiWorkbenchLayout>
  </AiModuleShell>
</template>

<style scoped>
.ai-generate-page__operation-stack,
.ai-generate-page__field {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.ai-generate-page__operation-stack {
  min-height: 0;
  flex: 1;
  gap: var(--space-5);
}

.ai-generate-page__field {
  gap: var(--space-2);
}

.ai-generate-page__field strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.ai-generate-page__actions {
  margin-top: auto;
  padding-top: var(--space-1);
}
</style>
