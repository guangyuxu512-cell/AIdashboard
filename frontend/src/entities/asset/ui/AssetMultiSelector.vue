<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'

import DataTable from '@/shared/components/DataTable.vue'
import { getErrorMessage } from '@/shared/api'
import { AppButton, AppDialog, AppInput } from '@/shared/ui'

import { useAssetListQuery } from '../api/asset-queries'
import type { AssetListItemViewModel } from '../model/types'
import AssetThumbnail from './AssetThumbnail.vue'

const props = withDefaults(
  defineProps<{ modelValue?: string[]; disabled?: boolean }>(),
  { modelValue: () => [], disabled: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const visible = ref(false)
const searchDraft = ref('')
const search = ref('')
const draftIds = ref<string[]>([])
const listQuery = useAssetListQuery(
  computed(() => ({ page: 1, pageSize: 100, search: search.value })),
)
const rows = computed(() => listQuery.data.value?.items ?? [])
const hasRows = computed(() => listQuery.data.value !== undefined)
const initialLoading = computed(() => listQuery.isPending.value && !hasRows.value)
const initialError = computed(() =>
  listQuery.error.value && !hasRows.value
    ? getErrorMessage(listQuery.error.value)
    : null,
)
const selectedRows = computed(() => {
  const byId = new Map(rows.value.map((row) => [row.assetId, row]))
  return props.modelValue.map((assetId) =>
    byId.get(assetId) ?? {
      assetId,
      filename: assetId,
      contentUrl: '',
      thumbnailUrl: '',
    },
  )
})

watch(visible, (show) => {
  if (show) draftIds.value = [...props.modelValue]
})

function updateDraft(keys: DataTableRowKey[]): void {
  const next = keys.map(String)
  const nextSet = new Set(next)
  draftIds.value = [
    ...draftIds.value.filter((id) => nextSet.has(id)),
    ...next.filter((id) => !draftIds.value.includes(id)),
  ]
}

function confirm(): void {
  emit('update:modelValue', [...draftIds.value])
  visible.value = false
}

function remove(assetId: string): void {
  emit(
    'update:modelValue',
    props.modelValue.filter((id) => id !== assetId),
  )
}

const columns: DataTableColumns<AssetListItemViewModel> = [
  { type: 'selection', width: 44 },
  {
    title: '图片',
    key: 'thumbnail',
    width: 80,
    render: (asset) =>
      h(AssetThumbnail, { src: asset.thumbnailUrl, alt: asset.filename }),
  },
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true } },
  { title: '大小', key: 'sizeDisplay', width: 100, align: 'center' },
  { title: '上传时间', key: 'createdAtDisplay', width: 160, align: 'center' },
]
</script>

<template>
  <div class="asset-multi-selector">
    <div class="asset-multi-selector__toolbar">
      <span class="asset-multi-selector__summary">
        {{ modelValue.length ? `已选择 ${modelValue.length} 张图片` : '未选择图片' }}
      </span>
      <AppButton :disabled="disabled" @click="visible = true">
        选择资料库图片
      </AppButton>
      <AppButton
        v-if="modelValue.length"
        tone="text"
        :disabled="disabled"
        @click="$emit('update:modelValue', [])"
      >
        清空
      </AppButton>
    </div>
    <div v-if="modelValue.length" class="asset-multi-selector__selected">
      <div
        v-for="asset in selectedRows"
        :key="asset.assetId"
        class="asset-multi-selector__selected-item"
      >
        <AssetThumbnail
          v-if="asset.thumbnailUrl"
          :src="asset.thumbnailUrl"
          :alt="asset.filename"
        />
        <span :title="asset.filename">{{ asset.filename }}</span>
        <AppButton tone="text" :disabled="disabled" @click="remove(asset.assetId)">
          移除
        </AppButton>
      </div>
    </div>

    <AppDialog
      v-model:show="visible"
      title="选择资料库图片"
      size="lg"
      positive-text="确认选择"
      @confirm="confirm"
    >
      <div class="asset-multi-selector__dialog">
        <div class="asset-multi-selector__search">
          <AppInput
            v-model="searchDraft"
            placeholder="搜索文件名"
            width="lg"
            clearable
          />
          <AppButton tone="primary" @click="search = searchDraft">查询</AppButton>
        </div>
        <DataTable
          :columns="columns"
          :data="rows"
          :loading="initialLoading"
          :error="initialError"
          :row-key="(row: AssetListItemViewModel) => row.assetId"
          :checked-row-keys="draftIds"
          :scroll-x="640"
          appearance="list"
          viewport="stable"
          empty-description="暂无可选择的图片"
          @update:checked-row-keys="updateDraft"
          @retry="listQuery.refetch()"
        />
      </div>
      <template #footer-start>已选择 {{ draftIds.length }} 张</template>
    </AppDialog>
  </div>
</template>

<style scoped>
.asset-multi-selector,
.asset-multi-selector__dialog {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.asset-multi-selector__toolbar,
.asset-multi-selector__search,
.asset-multi-selector__selected-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.asset-multi-selector__summary {
  color: var(--text-secondary);
}

.asset-multi-selector__selected {
  display: grid;
  gap: var(--space-2);
}

.asset-multi-selector__selected-item {
  min-width: 0;
  padding: var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-muted);
}

.asset-multi-selector__selected-item > span {
  overflow: hidden;
  flex: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
