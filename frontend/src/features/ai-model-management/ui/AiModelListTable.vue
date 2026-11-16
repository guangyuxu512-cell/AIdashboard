<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import {
  getAiModelCapabilityLabel,
  type AiModelViewModel,
} from '@/entities/ai-model'
import DataTable from '@/shared/components/DataTable.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  rows: AiModelViewModel[]
  loading?: boolean
  error?: string | null
  mutatingModelId?: string | null
}>()

const emit = defineEmits<{
  edit: [model: AiModelViewModel]
  'toggle-enabled': [model: AiModelViewModel]
  'set-default': [model: AiModelViewModel]
  retry: []
}>()

const columns: DataTableColumns<AiModelViewModel> = [
  {
    title: '模型名称',
    key: 'displayName',
    width: 150,
    fixed: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: 'Code',
    key: 'modelCode',
    width: 150,
    ellipsis: { tooltip: true },
  },
  {
    title: 'Provider',
    key: 'providerCode',
    width: 100,
    align: 'center',
    render: () => 'ToAPIs',
  },
  {
    title: '能力',
    key: 'capabilities',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (model) =>
      model.capabilities.map(getAiModelCapabilityLabel).join(' / '),
  },
  {
    title: '输入上限',
    key: 'maxInputImages',
    width: 96,
    align: 'center',
    render: (model) => `${model.maxInputImages} 张`,
  },
  {
    title: '默认',
    key: 'isDefault',
    width: 86,
    align: 'center',
    render: (model) =>
      model.isDefault ? h(StatusTag, { label: '默认', tone: 'info' }) : '—',
  },
  {
    title: '状态',
    key: 'enabled',
    width: 96,
    align: 'center',
    render: (model) =>
      h(StatusTag, {
        label: model.enabled ? '已启用' : '已停用',
        tone: model.enabled ? 'success' : 'neutral',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 224,
    align: 'center',
    fixed: 'right',
    render: (model) =>
      h('div', { class: 'ai-model-list__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('edit', model) },
          () => '编辑',
        ),
        ...(model.isDefault
          ? []
          : [
              h(
                AppButton,
                {
                  tone: 'text',
                  disabled: !model.enabled,
                  loading: props.mutatingModelId === model.modelId,
                  onClick: () => emit('set-default', model),
                },
                () => '设为默认',
              ),
            ]),
        h(
          AppButton,
          {
            tone: 'text',
            loading: props.mutatingModelId === model.modelId,
            disabled:
              model.isDefault ||
              (Boolean(props.mutatingModelId) &&
                props.mutatingModelId !== model.modelId),
            onClick: () => emit('toggle-enabled', model),
          },
          () => (model.enabled ? '停用' : '启用'),
        ),
      ]),
  },
]
</script>

<template>
  <DataTable
    class="ai-model-list"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: AiModelViewModel) => row.modelId"
    :scroll-x="1082"
    appearance="list"
    viewport="fill"
    empty-description="暂无模型"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.ai-model-list {
  min-height: 0;
  flex: 1;
}

:deep(.ai-model-list__actions) {
  display: flex;
  justify-content: center;
  gap: var(--space-1);
}
</style>
