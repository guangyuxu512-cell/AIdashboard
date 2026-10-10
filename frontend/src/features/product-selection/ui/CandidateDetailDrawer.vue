<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Copy } from '@lucide/vue'
import {
  NDescriptions,
  NDescriptionsItem,
  NText,
  NTooltip,
  NCollapse,
  NCollapseItem,
  NAlert,
  useMessage,
} from 'naive-ui'
import {
  DetailDrawer,
  ErrorState,
  LoadingState,
  StatusTag,
} from '@/shared/components'
import { AppButton } from '@/shared/ui'
import type { SelectionService } from '../model/contracts'
import {
  formatCandidateDate,
  formatCandidateTime,
  formatReviewRate,
  comparablePreviousRank,
  rankChange,
  collectionLabels,
  discoveryLabels,
  discoveryDescriptions,
  sourceProductUrl,
} from '../model/candidate-display'
import ExternalProductImage from './ExternalProductImage.vue'

const props = defineProps<{
  id: string | null
  service: SelectionService
  contextKey: string
}>()
const emit = defineEmits<{ close: []; updated: [] }>()
const message = useMessage()
const busy = ref(false)
const query = useQuery({
  queryKey: computed(() => ['selection-candidate', props.contextKey, props.id]),
  enabled: computed(() => !!props.id),
  queryFn: ({ queryKey }) => props.service.candidate(String(queryKey[2])),
  retry: false,
})
const row = computed(() => query.data.value)
const sourceUrl = computed(() => sourceProductUrl(row.value?.sourceUrl ?? null))
const change = computed(() => (row.value ? rankChange(row.value) : null))
const descriptionTheme = {
  thPaddingBorderedMedium: 'var(--space-3)',
  tdPaddingBorderedMedium: 'var(--space-3)',
  fontSizeMedium: 'var(--font-size-body)',
  thFontWeight: 'var(--font-weight-regular)',
  thTextColor: 'var(--text-secondary)',
  tdTextColor: 'var(--text-primary)',
}
const descriptionLabelStyle = { fontSize: 'var(--font-size-secondary)' }
const metrics = computed(() =>
  row.value
    ? [
        {
          label: '短视频用户支付金额',
          value: row.value.userPaidAmountRange,
          unit: row.value.userPaidAmountUnit,
          unknownUnit:
            !!row.value.userPaidAmountRange && !row.value.userPaidAmountUnit,
        },
        { label: '短视频点击次数', value: row.value.clicksRange },
        { label: '短视频成交件数', value: row.value.soldUnitsRange },
        { label: '带货视频数', value: row.value.videoCountRange },
      ]
    : [],
)
async function copyProductId() {
  if (!row.value) return
  try {
    await navigator.clipboard.writeText(row.value.productId)
    message.success('商品ID已复制')
  } catch {
    message.error('商品ID复制失败')
  }
}
async function act(action: 'collect' | 'metrics' | 'competitor') {
  if (busy.value || !row.value) return
  const id = row.value.id
  const contextKey = props.contextKey
  const merchantShopId = row.value.merchant?.shopId
  if (action === 'competitor' && !merchantShopId) {
    message.error('商品商家身份缺失，无法标记竞品店铺')
    return
  }
  busy.value = true
  try {
    const receipt =
      action === 'collect'
        ? await props.service.demoAction(id, 'collect')
        : action === 'metrics'
          ? await props.service.updateCompassMetrics(id)
          : await props.service.markCompetitor(merchantShopId!)
    if (props.id !== id || props.contextKey !== contextKey) return
    message.info(receipt.message)
    await query.refetch()
    emit('updated')
  } catch (error) {
    if (props.id === id && props.contextKey === contextKey)
      message.error(error instanceof Error ? error.message : '操作失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <DetailDrawer
    :show="!!id"
    title="候选商品详情"
    size="md"
    @update:show="!$event && emit('close')"
  >
    <LoadingState v-if="query.isPending.value" />
    <ErrorState
      v-else-if="query.isError.value"
      :description="query.error.value?.message"
      retryable
      @retry="query.refetch()"
    />
    <div v-else-if="row" class="candidate-detail">
      <NAlert
        v-if="row.basicInfoError"
        type="warning"
        title="商品补充信息未完成"
        >{{ row.basicInfoError }}</NAlert
      >
      <div class="candidate-detail__summary">
        <ExternalProductImage :src="row.imageUrl" :title="row.title" />
        <div class="candidate-detail__identity">
          <div class="candidate-detail__headline">
            <strong class="candidate-detail__title">{{ row.title }}</strong>
            <NTooltip>
              <template #trigger>
                <NText depth="3" class="candidate-detail__metadata"
                  >罗盘：{{ row.sourceContext.periodLabel || '—' }} · 更新
                  {{ formatCandidateTime(row.metricsRetrievedAt, 'MM-DD HH:mm')
                  }}{{
                    row.sourceContext.dateFallback ? ' · 已回退一天' : ''
                  }}</NText
                >
              </template>
              完整统计区间：{{ row.sourceContext.statisticalPeriod || '—' }}
              <br />
              指标获取时间：{{ formatCandidateTime(row.metricsRetrievedAt) }}
            </NTooltip>
          </div>
          <NText
            v-if="row.sourceContext.dateFallback !== undefined"
            depth="3"
            class="candidate-detail__metadata"
            >{{ row.sourceContext.statisticalPeriod || '—' }}</NText
          >
          <NText :depth="row.priceBand === null ? 3 : 1"
            >价格／价格带：{{ row.priceBand ?? '—' }}</NText
          >
        </div>
      </div>
      <section aria-label="罗盘视频数据">
        <h3>罗盘视频数据</h3>
        <NDescriptions
          :column="2"
          label-placement="top"
          bordered
          :theme-overrides="descriptionTheme"
          :label-style="descriptionLabelStyle"
        >
          <NDescriptionsItem
            v-for="metric in metrics"
            :key="metric.label"
            :label="metric.label"
          >
            <NTooltip :disabled="!metric.unknownUnit"
              ><template #trigger
                ><NText
                  tag="strong"
                  class="candidate-detail__metric"
                  :depth="metric.value === null ? 3 : 1"
                  >{{ metric.value ?? '—' }}</NText
                ></template
              >单位未确认</NTooltip
            >
            <template v-if="!metric.unknownUnit">{{ metric.unit }}</template>
          </NDescriptionsItem>
        </NDescriptions>
      </section>
      <section aria-label="排名与发现">
        <h3>排名与发现</h3>
        <NDescriptions
          :column="2"
          label-placement="top"
          bordered
          :theme-overrides="descriptionTheme"
          :label-style="descriptionLabelStyle"
        >
          <NDescriptionsItem label="所属榜单">{{
            row.sourceContext.leaderboardName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="本次排名">
            <NText :depth="row.rank === null ? 3 : 1">{{
              row.rank ?? '—'
            }}</NText>
            <NText v-if="change" :type="change.type" :depth="1">
              · {{ change.label }}</NText
            >
          </NDescriptionsItem>
          <NDescriptionsItem label="上次排名">
            <NTooltip
              :disabled="
                !row.previousRank || comparablePreviousRank(row) !== null
              "
              ><template #trigger
                ><NText :depth="row.previousRank === null ? 3 : 1">{{
                  row.previousRank?.rank ?? '—'
                }}</NText></template
              >口径不同，不作比较</NTooltip
            >
          </NDescriptionsItem>
          <NDescriptionsItem label="发现情况">
            <NTooltip
              ><template #trigger
                ><NText :depth="row.discovery === 'unknown' ? 3 : 1">{{
                  discoveryLabels[row.discovery]
                }}</NText></template
              >{{ discoveryDescriptions[row.discovery] }}</NTooltip
            >
          </NDescriptionsItem>
          <NDescriptionsItem label="首次发现时间"
            ><NText :depth="row.firstDiscoveredAt === null ? 3 : 1">{{
              formatCandidateTime(row.firstDiscoveredAt)
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="平台首次上榜"
            ><NText :depth="row.firstListed === null ? 3 : 1">{{
              row.firstListed === null ? '—' : row.firstListed ? '是' : '否'
            }}</NText></NDescriptionsItem
          >
        </NDescriptions>
      </section>
      <section aria-label="商品基础信息">
        <h3>商品基础信息</h3>
        <NDescriptions
          :column="1"
          label-placement="left"
          bordered
          :theme-overrides="descriptionTheme"
          :label-style="descriptionLabelStyle"
        >
          <NDescriptionsItem label="商品ID">
            <div class="candidate-detail__inline">
              <span>{{ row.productId }}</span>
              <AppButton
                tone="text"
                :aria-label="`复制商品ID ${row.productId}`"
                @click="copyProductId"
                ><Copy :size="16" aria-hidden="true"
              /></AppButton>
              <AppButton
                v-if="sourceUrl"
                tone="link"
                tag="a"
                :href="sourceUrl"
                target="_blank"
                rel="noopener noreferrer"
                >查看源商品</AppButton
              >
            </div>
          </NDescriptionsItem>
          <NDescriptionsItem label="商品所属商家">
            <div class="candidate-detail__inline">
              <NText :depth="row.merchant ? 1 : 3">{{
                row.merchant?.name ?? '—'
              }}</NText>
              <AppButton
                tone="secondary"
                :disabled="
                  busy ||
                  !service.available ||
                  !row.merchant?.shopId ||
                  row.merchant.competitor
                "
                @click="act('competitor')"
                >{{
                  row.merchant?.competitor ? '已标记竞品店铺' : '标记为竞品店铺'
                }}</AppButton
              >
            </div>
            <NText v-if="!row.merchant?.shopId" tag="div" depth="3"
              >商品商家身份未确认</NText
            >
          </NDescriptionsItem>
          <NDescriptionsItem label="完整类目">{{
            row.category
          }}</NDescriptionsItem>
          <NDescriptionsItem v-if="row.negativeReviewRateRaw" label="差评率">
            <NTooltip
              ><template #trigger
                ><NText depth="1">{{
                  row.negativeReviewRateRaw.value
                }}</NText></template
              >
              平台原值；unit={{
                row.negativeReviewRateRaw.unit ?? '—'
              }}，换算尚未确认
            </NTooltip>
          </NDescriptionsItem>
          <NDescriptionsItem v-else label="差评率"
            ><NText :depth="row.negativeReviewRate === null ? 3 : 1">{{
              formatReviewRate(row.negativeReviewRate)
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="首次上架日期"
            ><NText :depth="row.listedAt === null ? 3 : 1">{{
              formatCandidateDate(row.listedAt)
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="商品资料采集状态"
            ><NText v-if="row.collectionStatus === 'unknown'" depth="3">—</NText
            ><StatusTag
              v-else
              :label="collectionLabels[row.collectionStatus]"
              :tone="row.collectionStatus === 'failed' ? 'error' : 'neutral'"
          /></NDescriptionsItem>
          <NDescriptionsItem label="屏蔽状态">{{
            row.blocked ? '已屏蔽' : '未屏蔽'
          }}</NDescriptionsItem>
        </NDescriptions>
      </section>
      <section aria-label="数据来源">
        <NCollapse :key="id ?? 'closed'" :default-expanded-names="[]">
          <NCollapseItem title="数据来源" name="source">
            <template #header
              ><span class="candidate-detail__section-title"
                >数据来源</span
              ></template
            >
            <NDescriptions
              :column="1"
              label-placement="left"
              bordered
              :theme-overrides="descriptionTheme"
              :label-style="descriptionLabelStyle"
            >
              <NDescriptionsItem label="请求罗盘使用的自有店铺"
                ><NText depth="1">{{ row.shopName }}</NText></NDescriptionsItem
              >
              <NDescriptionsItem label="来源">{{
                row.source
              }}</NDescriptionsItem>
              <NDescriptionsItem label="完整统计区间">{{
                row.sourceContext.statisticalPeriod
              }}</NDescriptionsItem>
              <NDescriptionsItem label="类目范围">{{
                row.sourceContext.category
              }}</NDescriptionsItem>
              <NDescriptionsItem label="监控范围"
                >第<NText
                  :depth="row.sourceContext.rankFrom === null ? 3 : 1"
                  >{{ row.sourceContext.rankFrom ?? '—' }}</NText
                >–<NText :depth="row.sourceContext.rankTo === null ? 3 : 1">{{
                  row.sourceContext.rankTo ?? '—'
                }}</NText
                >名</NDescriptionsItem
              >
              <NDescriptionsItem label="榜单检查时间"
                ><NText :depth="row.sourceContext.checkedAt === null ? 3 : 1">{{
                  formatCandidateTime(row.sourceContext.checkedAt)
                }}</NText></NDescriptionsItem
              >
            </NDescriptions>
          </NCollapseItem>
        </NCollapse>
      </section>
    </div>
    <template #footer>
      <div class="candidate-detail__actions">
        <AppButton @click="emit('close')">关闭</AppButton>
        <AppButton
          tone="secondary"
          :disabled="!row || busy || !service.available"
          @click="act('metrics')"
          >更新罗盘指标</AppButton
        >
        <AppButton
          tone="primary"
          :disabled="!row || busy || !service.available"
          :loading="busy"
          @click="act('collect')"
          >采集资料</AppButton
        >
      </div>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.candidate-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-regular);
}
.candidate-detail__summary,
.candidate-detail__inline,
.candidate-detail__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.candidate-detail__inline {
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}
.candidate-detail__summary > :first-child {
  flex-shrink: 0;
}
.candidate-detail__identity {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}
.candidate-detail__headline {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
}
.candidate-detail__title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--font-size-page-title);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}
.candidate-detail__metadata {
  min-width: 0;
  max-width: 100%;
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-regular);
  overflow-wrap: anywhere;
}
.candidate-detail h3,
.candidate-detail__section-title {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.candidate-detail h3 {
  margin: 0 0 var(--space-2);
}
.candidate-detail__metric {
  font-size: 22px;
  font-weight: var(--font-weight-semibold);
}
.candidate-detail__actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}
</style>
