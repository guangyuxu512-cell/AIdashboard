<script setup lang="ts">
import dayjs from 'dayjs'
import { NDescriptions, NDescriptionsItem } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { AssetPreviewDialog } from '@/entities/asset'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  GENERATION_MODE_META,
  GENERATION_OUTPUT_FORMAT_META,
  GENERATION_RECORD_SOURCE_TYPE_META,
  GENERATION_RECORD_STATUS_META,
  type GenerationRecordView,
} from '../../generation/model/types'
import type {
  GenerationDownloadResult,
  GenerationDownloadSelection,
} from '../../generation/model/download'
import type {
  GenerationExecutionResultView,
  GenerationResultView,
} from '../../generation/model/types'
import BatchResultTree from '../../generation/ui/BatchResultTree.vue'
import InstantResultGrid from '../../generation/ui/InstantResultGrid.vue'

const props = defineProps<{
  show: boolean
  record: GenerationRecordView | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  retry: [record: GenerationRecordView]
  download: [selection: GenerationDownloadSelection]
}>()

const previewResultId = ref<string | null>(null)

watch(
  () => props.show,
  (show) => {
    if (!show) previewResultId.value = null
  },
)

function allResults(record: GenerationRecordView): GenerationDownloadResult[] {
  return record.detail.kind === 'INSTANT'
    ? record.detail.results
    : record.detail.results.flatMap((product) =>
        product.groups.flatMap((group) =>
          group.templates.flatMap((template) => template.results),
        ),
      )
}

function downloadAll(): void {
  if (!props.record) return
  emit('download', { scope: 'BATCH', results: allResults(props.record) })
}

const previewSources = computed(() =>
  props.record
    ? allResults(props.record)
        .filter(
          (result) => result.status === 'SUCCESS' && Boolean(result.previewUrl),
        )
        .map((result) => ({
          id: result.id,
          name:
            result.name ??
            ('slotIndex' in result
              ? `生成结果 ${result.slotIndex + 1}`
              : '生成结果'),
          contentUrl: result.previewUrl!,
        }))
    : [],
)

function previewResult(
  result: GenerationExecutionResultView | GenerationResultView,
): void {
  if (result.status !== 'SUCCESS' || !result.previewUrl) return
  previewResultId.value = result.id
}

function downloadPreviewResult(source: { id: string }): void {
  const result = props.record
    ? allResults(props.record).find((item) => item.id === source.id)
    : undefined
  if (result) emit('download', { scope: 'SINGLE', results: [result] })
}

function setPreviewVisible(visible: boolean): void {
  if (!visible) previewResultId.value = null
}
</script>

<template>
  <DetailDrawer
    :show="show"
    title="生成记录详情"
    size="lg"
    @update:show="$emit('update:show', $event)"
  >
    <template v-if="record" #header>
      <div class="generation-record-detail__header">
        <strong>{{
          GENERATION_RECORD_SOURCE_TYPE_META[record.sourceType].label
        }}</strong>
        <StatusTag
          :label="GENERATION_RECORD_STATUS_META[record.status].label"
          :tone="GENERATION_RECORD_STATUS_META[record.status].tone"
        />
      </div>
    </template>

    <div v-if="record" class="generation-record-detail">
      <section>
        <h3>任务信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="创建时间">
            {{ dayjs(record.createdAt).format('YYYY-MM-DD HH:mm:ss') }}
          </NDescriptionsItem>
          <NDescriptionsItem label="创建人">{{
            record.createdBy
          }}</NDescriptionsItem>
          <NDescriptionsItem label="生成模式">
            {{ GENERATION_MODE_META[record.mode].label }}
          </NDescriptionsItem>
          <NDescriptionsItem label="任务类型">
            {{ GENERATION_RECORD_SOURCE_TYPE_META[record.sourceType].label }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <template v-if="record.detail.kind === 'INSTANT'">
        <section>
          <h3>生成配置</h3>
          <NDescriptions :column="1" label-placement="left" bordered>
            <NDescriptionsItem
              v-for="slot in record.detail.inputSlots"
              :key="slot.key"
              :label="slot.label"
            >
              {{ slot.images.map((image) => image.name).join('、') || '—' }}
            </NDescriptionsItem>
            <NDescriptionsItem label="使用模板">
              {{ record.detail.templateName ?? '未使用' }}
            </NDescriptionsItem>
            <NDescriptionsItem label="提示词">
              {{ record.detail.effectiveConfig.prompt || '—' }}
            </NDescriptionsItem>
            <NDescriptionsItem label="输出格式">
              {{
                GENERATION_OUTPUT_FORMAT_META[
                  record.detail.effectiveConfig.outputFormat
                ].label
              }}
            </NDescriptionsItem>
            <NDescriptionsItem label="比例">
              {{ record.detail.effectiveConfig.size }}
            </NDescriptionsItem>
            <NDescriptionsItem label="数量">
              {{ record.detail.effectiveConfig.count }} 张
            </NDescriptionsItem>
          </NDescriptions>
        </section>
        <section>
          <h3>生成结果</h3>
          <InstantResultGrid
            :results="record.detail.results"
            :show-actions="false"
            @download="
              $emit('download', { scope: 'SINGLE', results: [$event] })
            "
            @preview="previewResult"
          />
        </section>
      </template>

      <template v-else>
        <section>
          <h3>执行统计</h3>
          <NDescriptions :column="2" label-placement="left" bordered>
            <NDescriptionsItem label="产品">{{
              record.detail.productCount
            }}</NDescriptionsItem>
            <NDescriptionsItem label="模板组">{{
              record.detail.templateGroupCount
            }}</NDescriptionsItem>
            <NDescriptionsItem label="生成项">{{
              record.detail.generationItemCount
            }}</NDescriptionsItem>
            <NDescriptionsItem label="成功">{{
              record.detail.successCount
            }}</NDescriptionsItem>
            <NDescriptionsItem label="失败">{{
              record.detail.failedCount
            }}</NDescriptionsItem>
          </NDescriptions>
        </section>
        <section>
          <h3>批量结果</h3>
          <BatchResultTree
            :results="record.detail.results"
            @download="$emit('download', $event)"
            @preview="previewResult"
          />
        </section>
      </template>
    </div>

    <template #footer>
      <div v-if="record" class="generation-record-detail__footer">
        <AppButton
          v-if="
            record.status === 'FAILED' || record.status === 'PARTIAL_FAILED'
          "
          @click="$emit('retry', record)"
        >
          重试失败项
        </AppButton>
        <span />
        <AppButton aria-label="下载全部生成结果" @click="downloadAll"
          >下载全部</AppButton
        >
        <AppButton @click="$emit('update:show', false)">关闭</AppButton>
      </div>
    </template>
  </DetailDrawer>
  <AssetPreviewDialog
    :show="Boolean(previewResultId)"
    :items="previewSources"
    :selected-asset-id="previewResultId"
    @update:show="setPreviewVisible"
    @download="downloadPreviewResult"
  />
</template>

<style scoped>
.generation-record-detail,
.generation-record-detail__header,
.generation-record-detail__footer {
  display: flex;
  min-width: 0;
}

.generation-record-detail {
  flex-direction: column;
  gap: var(--space-6);
}

.generation-record-detail__header {
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.generation-record-detail h3 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.generation-record-detail__footer {
  width: 100%;
  align-items: center;
  gap: var(--space-2);
}

.generation-record-detail__footer > span {
  flex: 1;
}
</style>
