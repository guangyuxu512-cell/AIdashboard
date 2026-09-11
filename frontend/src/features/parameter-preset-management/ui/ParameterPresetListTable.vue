<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import { h } from 'vue'
import dayjs from 'dayjs'

import type { AutomationParameterPresetDto } from '@/entities/automation-application'
import DataTable from '@/shared/components/DataTable.vue'
import { AppButton } from '@/shared/ui'

const props = defineProps<{
  rows: AutomationParameterPresetDto[]
  appNameById: ReadonlyMap<string, string>
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  edit: [preset: AutomationParameterPresetDto]
  copy: [preset: AutomationParameterPresetDto]
  retry: []
}>()

function parameterSummary(values: Record<string, unknown>): string {
  const entries = Object.entries(values)
  if (!entries.length) return '—'
  return entries
    .map(([name, value]) => `${name}=${String(value)}`)
    .join('；')
}

function appName(preset: AutomationParameterPresetDto): string {
  return props.appNameById.get(preset.app_id) ?? preset.app_id
}

const columns: DataTableColumns<AutomationParameterPresetDto> = [
  {
    title: '配置名',
    key: 'name',
    width: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: '应用',
    key: 'app_id',
    width: 220,
    ellipsis: { tooltip: true },
    render: (preset) => appName(preset),
  },
  {
    title: '公共参数',
    key: 'common_parameters',
    minWidth: 260,
    ellipsis: { tooltip: true },
    render: (preset) => parameterSummary(preset.common_parameters),
  },
  {
    title: '店铺差异',
    key: 'shop_overrides',
    width: 110,
    render: (preset) => `${Object.keys(preset.shop_overrides).length} 家`,
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 170,
    render: (preset) => dayjs(preset.updated_at).format('YYYY-MM-DD HH:mm'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (preset) =>
      h('div', { class: 'parameter-preset-list-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('edit', preset) },
          { default: () => '编辑' },
        ),
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('copy', preset) },
          { default: () => '复制' },
        ),
      ]),
  },
]
</script>

<template>
  <DataTable
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: AutomationParameterPresetDto) => row.preset_id"
    :scroll-x="1080"
    viewport="fill"
    empty-description="暂无参数配置"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
:deep(.parameter-preset-list-table__actions) {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
