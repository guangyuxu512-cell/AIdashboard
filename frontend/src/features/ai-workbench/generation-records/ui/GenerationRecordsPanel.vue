<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { ref } from 'vue'
import { storeToRefs } from 'pinia'

import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppInput, AppSelect } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import {
  GENERATION_MODE_META,
  GENERATION_RECORD_SOURCE_TYPE_META,
  GENERATION_RECORD_STATUS_META,
  type GenerationMode,
  type GenerationRecordSourceType,
  type GenerationRecordStatus,
  type GenerationRecordView,
} from '../../generation/model/types'
import { useAiGenerationStore } from '../../generation/model/useAiGenerationStore'
import GenerationRecordDetailDrawer from './GenerationRecordDetailDrawer.vue'
import GenerationRecordsTable from './GenerationRecordsTable.vue'

const generationStore = useAiGenerationStore()
const {
  visibleRecords,
  filteredRecords,
  recordsSearch,
  recordsSourceType,
  recordsMode,
  recordsStatus,
  recordsPage,
  recordsPageSize,
} = storeToRefs(generationStore)
const message = useMessage()
const detailVisible = ref(false)
const selectedRecord = ref<GenerationRecordView | null>(null)
const recordsSearchDraft = ref(recordsSearch.value)
const autoSearch = useAutoSearch(() => {
  generationStore.setRecordsSearch(recordsSearchDraft.value)
})

const sourceTypeOptions = [
  { label: '全部类型', value: 'ALL' },
  {
    label: GENERATION_RECORD_SOURCE_TYPE_META.INSTANT.label,
    value: 'INSTANT',
  },
  { label: GENERATION_RECORD_SOURCE_TYPE_META.BATCH.label, value: 'BATCH' },
]
const modeOptions = [
  { label: '全部模式', value: 'ALL' },
  {
    label: GENERATION_MODE_META.NORMAL_GENERATION.label,
    value: 'NORMAL_GENERATION',
  },
  {
    label: GENERATION_MODE_META.STYLE_REPLICATION.label,
    value: 'STYLE_REPLICATION',
  },
]
const statusOptions = [
  { label: '全部状态', value: 'ALL' },
  { label: GENERATION_RECORD_STATUS_META.RUNNING.label, value: 'RUNNING' },
  { label: GENERATION_RECORD_STATUS_META.SUCCESS.label, value: 'SUCCESS' },
  {
    label: GENERATION_RECORD_STATUS_META.PARTIAL_FAILED.label,
    value: 'PARTIAL_FAILED',
  },
  { label: GENERATION_RECORD_STATUS_META.FAILED.label, value: 'FAILED' },
]

function openDetail(record: GenerationRecordView): void {
  selectedRecord.value = record
  detailVisible.value = true
}

function setSourceType(value: string | number | null): void {
  if (value) {
    generationStore.setRecordsSourceType(
      value as 'ALL' | GenerationRecordSourceType,
    )
  }
}

function setMode(value: string | number | null): void {
  if (value) generationStore.setRecordsMode(value as 'ALL' | GenerationMode)
}

function setStatus(value: string | number | null): void {
  if (value) {
    generationStore.setRecordsStatus(value as 'ALL' | GenerationRecordStatus)
  }
}

function retry(record: GenerationRecordView): void {
  if (generationStore.retryFailedRecord(record.id))
    message.success('失败项已重试')
}

function download(): void {
  message.success('下载任务已创建')
}
</script>

<template>
  <div class="generation-records-panel" aria-label="生成记录列表">
    <FilterBar>
      <AppInput
        v-model="recordsSearchDraft"
        width="lg"
        clearable
        placeholder="搜索任务、内容或创建人"
        aria-label="搜索生成记录"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(recordsSearchDraft)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
      <AppSelect
        :model-value="recordsSourceType"
        :options="sourceTypeOptions"
        width="sm"
        aria-label="任务类型"
        @update:model-value="setSourceType"
      />
      <AppSelect
        :model-value="recordsMode"
        :options="modeOptions"
        width="sm"
        aria-label="生成模式"
        @update:model-value="setMode"
      />
      <AppSelect
        :model-value="recordsStatus"
        :options="statusOptions"
        width="sm"
        aria-label="任务状态"
        @update:model-value="setStatus"
      />
    </FilterBar>

    <ManagementListSection>
      <GenerationRecordsTable :records="visibleRecords" @detail="openDetail" />
      <PaginationBar
        :page="recordsPage"
        :page-size="recordsPageSize"
        :item-count="filteredRecords.length"
        @update:page="generationStore.setRecordsPage"
        @update:page-size="generationStore.setRecordsPageSize"
      />
    </ManagementListSection>
  </div>

  <GenerationRecordDetailDrawer
    v-model:show="detailVisible"
    :record="selectedRecord"
    @retry="retry"
    @download="download"
  />
</template>

<style scoped>
.generation-records-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}
</style>
