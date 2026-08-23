<script setup lang="ts">
import { useMessage, type DataTableColumns } from 'naive-ui'
import { h } from 'vue'

import type { ProviderApplicationViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  show: boolean
  applications: ProviderApplicationViewModel[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
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
          { tone: 'text', onClick: () => emit('run', application) },
          { default: () => '运行' },
        ),
      ]),
  },
]
</script>

<template>
  <DetailDrawer
    :show="show"
    title="影刀应用列表"
    size="lg"
    @update:show="$emit('update:show', $event)"
  >
    <p class="yingdao-applications__description">
      当前设备 6.3.6 登录账号可访问的云端应用。参数配置属于中控台配置，运行将创建正式 Task。
    </p>
    <DataTable
      :columns="columns"
      :data="applications"
      :row-key="(row: ProviderApplicationViewModel) => row.appId"
      :scroll-x="600"
      empty-description="当前账号没有已发现应用"
    />

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.yingdao-applications__description {
  margin-bottom: var(--space-4);
  color: var(--color-text-secondary);
}

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
