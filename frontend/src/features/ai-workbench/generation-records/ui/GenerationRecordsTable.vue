<script setup lang="ts">
import dayjs from 'dayjs'
import type { DataTableColumns } from 'naive-ui'
import { h } from 'vue'

import DataTable from '@/shared/components/DataTable.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import {
  GENERATION_MODE_META,
  GENERATION_RECORD_SOURCE_TYPE_META,
  GENERATION_RECORD_STATUS_META,
  type GenerationRecordView,
} from '../../generation/model/types'

defineProps<{
  records: GenerationRecordView[]
}>()

const emit = defineEmits<{
  detail: [record: GenerationRecordView]
}>()

const columns: DataTableColumns<GenerationRecordView> = [
  {
    title: '时间',
    key: 'createdAt',
    width: 150,
    render: (record) => dayjs(record.createdAt).format('YYYY-MM-DD HH:mm'),
  },
  {
    title: '类型',
    key: 'sourceType',
    width: 90,
    align: 'center',
    render: (record) =>
      GENERATION_RECORD_SOURCE_TYPE_META[record.sourceType].label,
  },
  {
    title: '模式',
    key: 'mode',
    width: 100,
    align: 'center',
    render: (record) => GENERATION_MODE_META[record.mode].label,
  },
  {
    title: '内容',
    key: 'summary',
    width: 210,
    ellipsis: { tooltip: true },
  },
  {
    title: '创建人',
    key: 'createdBy',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '结果',
    key: 'resultSummary',
    width: 145,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    align: 'center',
    render: (record) => {
      const meta = GENERATION_RECORD_STATUS_META[record.status]
      return h(StatusTag, { label: meta.label, tone: meta.tone })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render: (record) =>
      h(
        AppButton,
        { tone: 'text', onClick: () => emit('detail', record) },
        () => '查看',
      ),
  },
]
</script>

<template>
  <DataTable
    class="generation-records-table"
    :columns="columns"
    :data="records"
    :row-key="(record: GenerationRecordView) => record.id"
    :scroll-x="975"
    appearance="list"
    viewport="fill"
    empty-description="暂无生成记录"
  />
</template>

<style scoped>
.generation-records-table {
  min-height: 0;
  flex: 1;
}
</style>
