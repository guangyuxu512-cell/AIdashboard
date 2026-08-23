<script setup lang="ts">
import { useMessage, type DataTableColumns } from 'naive-ui'
import { h } from 'vue'

import type { ProviderApplicationViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = withDefaults(
  defineProps<{
    applications: ProviderApplicationViewModel[]
    canRun?: boolean
  }>(),
  { canRun: true },
)

const emit = defineEmits<{
  configure: [application: ProviderApplicationViewModel]
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
        { tone: 'text', onClick: () => emit('configure', application) },
        { default: () => '配置' },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (application) =>
      h('div', { class: 'yingdao-app-actions' }, [
        h(
          AppButton,
          {
            tone: 'text',
            disabled: !props.canRun,
            onClick: () => emit('run', application),
          },
          { default: () => '运行' },
        ),
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
    empty-description="当前账号没有已发现应用"
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
</style>
