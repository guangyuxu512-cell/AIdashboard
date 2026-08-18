<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'

import type { ProviderApplicationViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  show: boolean
  applications: ProviderApplicationViewModel[]
}>()

defineEmits<{ 'update:show': [value: boolean] }>()

const columns: DataTableColumns<ProviderApplicationViewModel> = [
  { title: '应用名称', key: 'appName', minWidth: 180 },
  {
    title: 'App ID',
    key: 'appId',
    minWidth: 300,
    ellipsis: { tooltip: true },
  },
  { title: 'Version', key: 'packageVersion', width: 100 },
  { title: 'Entrypoint', key: 'entrypoint', width: 120 },
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
      当前设备登录账号已同步到本机的影刀应用；不代表中控台已注册 Skill。
    </p>
    <DataTable
      :columns="columns"
      :data="applications"
      :row-key="(row: ProviderApplicationViewModel) => row.appId"
      :scroll-x="700"
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
</style>
