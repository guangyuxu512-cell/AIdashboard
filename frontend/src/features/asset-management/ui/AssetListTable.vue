<script setup lang="ts">
import { h, type VNodeChild } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import { AssetThumbnail, type AssetListItemViewModel } from '@/entities/asset'
import DataTable from '@/shared/components/DataTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  rows: AssetListItemViewModel[]
  loading?: boolean
  error?: string | null
}>()
const emit = defineEmits<{
  remove: [asset: AssetListItemViewModel]
  retry: []
}>()

function centered(child: VNodeChild) {
  return h('div', { class: 'asset-table__center' }, [child])
}

const columns: DataTableColumns<AssetListItemViewModel> = [
  {
    title: '图片',
    key: 'thumbnail',
    width: 90,
    render: (asset) =>
      centered(h(AssetThumbnail, { src: asset.contentUrl, alt: asset.filename })),
  },
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true } },
  { title: '大小', key: 'sizeDisplay', width: 120, align: 'center' },
  { title: '上传时间', key: 'createdAtDisplay', width: 180, align: 'center' },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    render: (asset) =>
      centered(
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('remove', asset) },
          () => '删除',
        ),
      ),
  },
]
</script>

<template>
  <DataTable
    class="asset-list-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: AssetListItemViewModel) => row.assetId"
    :scroll-x="760"
    appearance="list"
    viewport="fill"
    empty-description="暂无图片，上传后可在运行影刀应用时选择。"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.asset-list-table {
  min-height: 0;
  flex: 1;
}

:deep(.asset-table__center) {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
