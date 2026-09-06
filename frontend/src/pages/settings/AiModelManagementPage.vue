<script setup lang="ts">
import { Plus } from '@lucide/vue'

import {
  AiModelFormDialog,
  AiModelListTable,
  useAiModelManagement,
  type AiModelStatusFilter,
} from '@/features/ai-model-management'
import SettingsLayout from '@/features/system-settings/ui/SettingsLayout.vue'
import TableToolbar from '@/shared/components/TableToolbar.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

const management = useAiModelManagement()
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '已启用', value: 'enabled' },
  { label: '已停用', value: 'disabled' },
]

function setStatus(value: string | number | null): void {
  if (value === 'all' || value === 'enabled' || value === 'disabled')
    management.statusFilter.value = value as AiModelStatusFilter
}
</script>

<template>
  <SettingsLayout>
    <div class="ai-model-management-page">
      <TableToolbar class="ai-model-management-page__toolbar">
        <h1>AI 模型管理</h1>
        <template #actions>
          <AppSelect
            :model-value="management.statusFilter.value"
            :options="statusOptions"
            aria-label="模型状态"
            width="sm"
            @update:model-value="setStatus"
          />
          <AppButton tone="primary" @click="management.openCreate">
            <Plus :size="16" />
            新增模型
          </AppButton>
        </template>
      </TableToolbar>

      <div class="ai-model-management-page__table">
        <AiModelListTable
          :rows="management.visibleModels.value"
          :loading="management.loading.value"
          :error="management.error.value"
          :mutating-model-id="management.mutatingModelId.value"
          @edit="management.openEdit"
          @toggle-enabled="management.toggleEnabled"
          @set-default="management.setDefault"
          @retry="management.retry"
        />
      </div>

      <AiModelFormDialog
        :show="management.formVisible.value"
        :model="management.selectedModel.value"
        :submitting="management.formSubmitting.value"
        @update:show="management.formVisible.value = $event"
        @save="management.save"
      />
    </div>
  </SettingsLayout>
</template>

<style scoped>
.ai-model-management-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-4);
}

.ai-model-management-page__table {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.ai-model-management-page__toolbar {
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.ai-model-management-page__toolbar h1 {
  font-size: var(--font-size-page-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-compact);
}
</style>
