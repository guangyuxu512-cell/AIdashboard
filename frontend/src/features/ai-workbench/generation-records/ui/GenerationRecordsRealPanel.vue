<script setup lang="ts">
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'

import {
  AssetDownloadStatusBar,
  formatAssetDownloadFailure,
  useAssetDownloadQueue,
} from '@/entities/asset'
import {
  aiWorkbenchApi,
  aiWorkbenchQueryKeys,
  useGenerationJobQuery,
  useGenerationJobsQuery,
} from '@/entities/ai-workbench'
import type {
  GenerationJobListQuery,
  GenerationJobStatus,
  GenerationMode,
  GenerationWorkMode,
} from '@/entities/ai-workbench'
import { getErrorMessage } from '@/shared/api'
import FilterBar from '@/shared/components/FilterBar.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppSelect } from '@/shared/ui'

import {
  GENERATION_MODE_META,
  GENERATION_RECORD_SOURCE_TYPE_META,
  GENERATION_RECORD_STATUS_META,
  type GenerationRecordView,
} from '../../generation/model/types'
import {
  mapGenerationRecord,
  mapGenerationRecordSummary,
} from '../../real-api/model/mappers'
import GenerationRecordDetailDrawer from './GenerationRecordDetailDrawer.vue'
import GenerationRecordsTable from './GenerationRecordsTable.vue'

const message = useMessage()
const queryClient = useQueryClient()
const downloads = useAssetDownloadQueue()
const page = ref(1)
const pageSize = ref(20)
const sourceType = ref<'ALL' | GenerationWorkMode>('ALL')
const mode = ref<'ALL' | GenerationMode>('ALL')
const status = ref<'ALL' | GenerationJobStatus>('ALL')
const selectedJobId = ref<string | null>(null)
const detailVisible = ref(false)

const listQueryParams = computed<GenerationJobListQuery>(() => ({
  page: page.value,
  pageSize: pageSize.value,
  workMode: sourceType.value === 'ALL' ? undefined : sourceType.value,
  mode: mode.value === 'ALL' ? undefined : mode.value,
  status: status.value === 'ALL' ? undefined : status.value,
}))
const listQuery = useGenerationJobsQuery(listQueryParams)
const detailQuery = useGenerationJobQuery(selectedJobId, { poll: true })
const records = computed(() =>
  (listQuery.data.value?.items ?? []).map(mapGenerationRecordSummary),
)
const selectedRecord = computed<GenerationRecordView | null>(() =>
  detailQuery.data.value ? mapGenerationRecord(detailQuery.data.value) : null,
)

const retryMutation = useMutation({
  mutationFn: async (record: GenerationRecordView) => {
    const job = detailQuery.data.value
    if (!job || job.generation_job_id !== record.id) return null
    const items = job.items
      .filter((item) => item.status === 'FAILED')
      .map((item) => ({
        item_id: item.generation_item_id,
        expected_attempt_count: item.attempt_count,
      }))
    if (!items.length) return null
    return aiWorkbenchApi.retryGenerationItems(job.generation_job_id, { items })
  },
  onSuccess: (job) => {
    if (!job) return
    queryClient.setQueryData(
      aiWorkbenchQueryKeys.generationJob(job.generation_job_id),
      job,
    )
    void queryClient.invalidateQueries({
      queryKey: aiWorkbenchQueryKeys.generations,
    })
    message.success('失败项已重试')
  },
  onError: (error) => message.error(getErrorMessage(error)),
})

const sourceTypeOptions = [
  { label: '全部类型', value: 'ALL' },
  { label: GENERATION_RECORD_SOURCE_TYPE_META.INSTANT.label, value: 'INSTANT' },
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
  { label: GENERATION_RECORD_STATUS_META.QUEUED.label, value: 'PENDING' },
  { label: GENERATION_RECORD_STATUS_META.RUNNING.label, value: 'RUNNING' },
  { label: GENERATION_RECORD_STATUS_META.SUCCESS.label, value: 'SUCCESS' },
  {
    label: GENERATION_RECORD_STATUS_META.PARTIAL_FAILED.label,
    value: 'PARTIAL_FAILED',
  },
  { label: GENERATION_RECORD_STATUS_META.FAILED.label, value: 'FAILED' },
]

function openDetail(record: GenerationRecordView): void {
  selectedJobId.value = record.id
  detailVisible.value = true
}

function updateSourceType(value: string | number | null): void {
  if (value === 'ALL' || value === 'INSTANT' || value === 'BATCH') {
    sourceType.value = value
    page.value = 1
  }
}

function updateMode(value: string | number | null): void {
  if (
    value === 'ALL' ||
    value === 'NORMAL_GENERATION' ||
    value === 'STYLE_REPLICATION'
  ) {
    mode.value = value
    page.value = 1
  }
}

function updateStatus(value: string | number | null): void {
  if (
    value === 'ALL' ||
    value === 'PENDING' ||
    value === 'RUNNING' ||
    value === 'SUCCESS' ||
    value === 'PARTIAL_FAILED' ||
    value === 'FAILED'
  ) {
    status.value = value
    page.value = 1
  }
}

function setPageSize(value: number): void {
  pageSize.value = value
  page.value = 1
}

function retry(record: GenerationRecordView): void {
  retryMutation.mutate(record)
}

function download(): void {
  if (downloads.isDownloading.value) return
  const results = selectedRecord.value?.detail
  const outputResults =
    results?.kind === 'INSTANT'
      ? results.results
      : (results?.results.flatMap((product) =>
          product.groups.flatMap((group) =>
            group.templates.flatMap((template) => template.results),
          ),
        ) ?? [])
  const downloadable =
    outputResults?.filter(
      (result) => result.status === 'SUCCESS' && result.previewUrl,
    ) ?? []
  const requests = downloadable.flatMap((result) =>
    result.previewUrl
      ? [
          {
            id: result.id,
            contentUrl: result.previewUrl,
            filename: result.name || 'generation.png',
          },
        ]
      : [],
  )
  void downloads.start(requests).then((summary) => {
    if (!summary) return
    if (summary.succeeded) message.success(`已开始下载 ${summary.succeeded} 张图片`)
    if (summary.failed) {
      const firstFailure = summary.results.find((result) => result.failure)?.failure
      if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
    }
  })
}

function retryFailedDownloads(): void {
  void downloads.retryFailed().then((summary) => {
    if (!summary) return
    if (summary.succeeded) message.success(`已重新下载 ${summary.succeeded} 张图片`)
    if (summary.failed) {
      const firstFailure = summary.results.find((result) => result.failure)?.failure
      if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
    }
  })
}
</script>

<template>
  <div class="generation-records-panel" aria-label="生成记录列表">
    <FilterBar>
      <AppSelect
        :model-value="sourceType"
        :options="sourceTypeOptions"
        width="sm"
        aria-label="任务类型"
        @update:model-value="updateSourceType"
      />
      <AppSelect
        :model-value="mode"
        :options="modeOptions"
        width="sm"
        aria-label="生成模式"
        @update:model-value="updateMode"
      />
      <AppSelect
        :model-value="status"
        :options="statusOptions"
        width="sm"
        aria-label="任务状态"
        @update:model-value="updateStatus"
      />
    </FilterBar>

    <ManagementListSection>
      <LoadingState
        v-if="listQuery.isPending.value"
        description="正在加载生成记录"
      />
      <ErrorState
        v-else-if="listQuery.isError.value"
        :description="getErrorMessage(listQuery.error.value)"
        retryable
        @retry="listQuery.refetch()"
      />
      <GenerationRecordsTable v-else :records="records" @detail="openDetail" />
      <PaginationBar
        :page="page"
        :page-size="pageSize"
        :item-count="listQuery.data.value?.total ?? 0"
        @update:page="page = $event"
        @update:page-size="setPageSize"
      />
    </ManagementListSection>
  </div>

  <GenerationRecordDetailDrawer
    v-model:show="detailVisible"
    :record="selectedRecord"
    @retry="retry"
    @download="download"
  />
  <AssetDownloadStatusBar
    :is-downloading="downloads.isDownloading.value"
    :progress-label="downloads.progressLabel.value"
    :failed-count="downloads.failedRequests.value.length"
    @cancel="downloads.cancel"
    @retry-failed="retryFailedDownloads"
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
