<script setup lang="ts">
import { NTooltip, useMessage, type DataTableColumns } from 'naive-ui'
import { h } from 'vue'

import type { ProviderApplicationViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = withDefaults(
  defineProps<{
    applications: ProviderApplicationViewModel[]
    runDisabledReason?: string | null
  }>(),
  { runDisabledReason: null },
)

const emit = defineEmits<{
  parameterPresets: [application: ProviderApplicationViewModel]
  run: [application: ProviderApplicationViewModel]
}>()
const message = useMessage()

async function copyAppId(appId: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(appId)
    message.success('App ID 已复制')
  } catch {
    message.error('App ID 复制失败')
  }
}

function getRunDisabledReason(
  application: ProviderApplicationViewModel,
): string | null {
  if (props.runDisabledReason) return props.runDisabledReason
  if (!application.appId.trim() || !application.appName.trim()) {
    return '当前 Application 不可用'
  }
  return null
}

function renderRunButton(application: ProviderApplicationViewModel) {
  const disabledReason = getRunDisabledReason(application)
  const button = h(
    AppButton,
    {
      tone: 'text',
      disabled: Boolean(disabledReason),
      onClick: () => emit('run', application),
    },
    { default: () => '运行' },
  )
  if (!disabledReason) return button
  return h(
    NTooltip,
    { placement: 'top' },
    {
      trigger: () => h('span', { class: 'yingdao-run-disabled' }, [button]),
      default: () => disabledReason,
    },
  )
}

const columns: DataTableColumns<ProviderApplicationViewModel> = [
  { title: '应用名称', key: 'appName', minWidth: 180 },
  {
    title: 'App ID',
    key: 'appId',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (application) =>
      h('div', { class: 'yingdao-app-id' }, [
        h('span', application.appId),
        h(
          AppButton,
          { tone: 'text', onClick: () => copyAppId(application.appId) },
          { default: () => '复制' },
        ),
      ]),
  },
  {
    title: '参数配置',
    key: 'configuration',
    width: 100,
    render: (application) =>
      h(
        AppButton,
        {
          tone: 'text',
          onClick: () => emit('parameterPresets', application),
        },
        { default: () => '参数配置' },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (application) =>
      h('div', { class: 'yingdao-app-actions' }, [
        renderRunButton(application),
      ]),
  },
]
</script>

<template>
  <DataTable
    :columns="columns"
    :data="applications"
    :row-key="(row: ProviderApplicationViewModel) => row.appId"
    :scroll-x="600"
    empty-description="暂无可访问的影刀应用"
  />
</template>

<style scoped>
:deep(.yingdao-app-id),
:deep(.yingdao-app-actions) {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

:deep(.yingdao-app-id span) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.yingdao-run-disabled) {
  display: inline-flex;
}
</style>
