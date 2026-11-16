<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Copy } from '@lucide/vue'
import {
  NDescriptions,
  NDescriptionsItem,
  NText,
  NTooltip,
  NCollapse,
  NCollapseItem,
  NConfigProvider,
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
  formatFirstListed,
  comparablePreviousRank,
  rankChange,
  collectionLabels,
  discoveryLabels,
  discoveryDescriptions,
  sourceProductUrl,
} from '../model/candidate-display'
import ExternalProductImage from './ExternalProductImage.vue'
import {
  basicRunStatus,
  basicStatus,
  basicFieldHint,
} from '../model/basic-display'

const props = defineProps<{
  id: string | null
  service: SelectionService
  contextKey: string
  receiptId?: string | null
}>()
const emit = defineEmits<{ close: []; updated: [] }>()
const message = useMessage()
const busy = ref(false)
const query = useQuery({
  queryKey: computed(() => [
    'selection-candidate',
    props.contextKey,
    props.id,
    props.receiptId ?? null,
  ]),
  enabled: computed(() => !!props.id),
  queryFn: ({ queryKey }) =>
    props.service.candidate(String(queryKey[2]), queryKey[3] as string | null),
  retry: false,
})
const row = computed(() => query.data.value)
const capabilities = useQuery({
  queryKey: computed(() => ['selection-capabilities', props.contextKey]),
  enabled: computed(() => !!props.id && !!props.service.manual),
  queryFn: () => props.service.manual!.capabilities(),
  retry: false,
})
const basicRun = useQuery({
  queryKey: computed(() => ['selection-basic-run', props.contextKey, props.id]),
  enabled: computed(() => !!props.id && !!props.service.basic),
  queryFn: ({ queryKey }) => props.service.basic!.latest(String(queryKey[2])),
  retry: false,
  refetchInterval: (query) =>
    ['pending', 'running'].includes(query.state.data?.status ?? '')
      ? 1000
      : false,
})
const basicBusy = computed(
  () =>
    busy.value ||
    ['pending', 'running'].includes(basicRun.data.value?.status ?? ''),
)
const basicFeedback = computed(() => {
  const run = basicRun.data.value
  if (run)
    return run.status === 'succeeded'
      ? '上次基础信息已更新'
      : basicRunStatus(run)
  return row.value?.basicInfoStatus?.state === 'succeeded'
    ? '上次基础信息已更新'
    : (basicStatus(row.value?.basicInfoStatus) ??
        row.value?.basicInfoError ??
        null)
})
const basicKey = ref<string | null>(null)
watch(
  () => [props.id, props.contextKey],
  () => {
    basicKey.value = null
  },
)
watch(
  () => basicRun.data.value?.status,
  (value, previous) => {
    if (
      value &&
      previous &&
      ['pending', 'running'].includes(previous) &&
      !['pending', 'running'].includes(value)
    ) {
      if (value === 'succeeded')
        message.success(basicRunStatus(basicRun.data.value!))
      else message.warning(basicRunStatus(basicRun.data.value!))
      void query.refetch()
      emit('updated')
    }
  },
)
async function updateBasic() {
  if (!row.value || basicBusy.value) return
  if (!props.service.basic) {
    await act('metrics')
    return
  }
  const id = row.value.id,
    contextKey = props.contextKey
  busy.value = true
  try {
    basicKey.value ??= crypto.randomUUID()
    const receipt = await props.service.basic.submit(id, basicKey.value)
    if (props.id !== id || props.contextKey !== contextKey) return
    basicKey.value = null
    message.info(
      receipt.reused ? '已复用正在进行的基础信息更新' : '基础信息更新已排队',
    )
    await basicRun.refetch()
  } catch (error) {
    if (props.id === id && props.contextKey === contextKey)
      message.error(error instanceof Error ? error.message : '基础信息提交失败')
    // Keep the same key after an uncertain HTTP receipt; retry cannot create two runs.
  } finally {
    busy.value = false
  }
}
const sourceUrl = computed(() => sourceProductUrl(row.value?.sourceUrl ?? null))
const change = computed(() => (row.value ? rankChange(row.value) : null))
const descriptionTheme = {
  thPaddingBorderedMedium: 'var(--space-2)',
  tdPaddingBorderedMedium: 'var(--space-2)',
  fontSizeMedium: 'var(--font-size-secondary)',
  thFontWeight: 'var(--font-weight-regular)',
  thTextColor: 'var(--text-secondary)',
  tdTextColor: 'var(--text-primary)',
}
const descriptionLabelStyle = { fontSize: 'var(--font-size-secondary)' }
// Detail-only sizing; keep the shared Drawer, colors and other consumers intact.
const detailTheme = {
  Button: {
    heightSmall: 'var(--list-compact-control-height)',
    heightMedium: 'var(--list-compact-control-height)',
    fontSizeSmall: 'var(--font-size-secondary)',
    fontSizeMedium: 'var(--font-size-secondary)',
  },
}
const metrics = computed(() =>
  row.value
    ? [
        {
          label: '短视频用户支付金额',
          value: row.value.userPaidAmountRange,
          unit: row.value.userPaidAmountUnit,
          unknownUnit:
            !!row.value.userPaidAmountRange &&
            !row.value.userPaidAmountRange.startsWith('¥') &&
            !row.value.userPaidAmountUnit,
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
  <NConfigProvider abstract :theme-overrides="detailTheme">
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
        <div class="candidate-detail__summary">
          <ExternalProductImage :src="row.imageUrl" :title="row.title" />
          <div class="candidate-detail__identity">
            <div class="candidate-detail__headline">
              <strong class="candidate-detail__title">{{ row.title }}</strong>
              <NTooltip>
                <template #trigger>
                  <NText depth="3" class="candidate-detail__metadata"
                    >罗盘：{{ row.sourceContext.periodLabel || '—' }} · 更新
                    {{
                      formatCandidateTime(
                        row.metricsRetrievedAt,
                        'MM-DD HH:mm',
                      )
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
                formatFirstListed(row.firstListed)
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
                    row.merchant?.competitor
                      ? '已标记竞品店铺'
                      : '标记为竞品店铺'
                  }}</AppButton
                >
              </div>
              <NText
                v-if="!row.merchant?.shopId"
                tag="div"
                depth="3"
                class="candidate-detail__metadata"
                >商品商家身份未确认</NText
              >
            </NDescriptionsItem>
            <NDescriptionsItem label="完整类目"
              ><NTooltip :disabled="!row.basicInfoStatus"
                ><template #trigger
                  ><NText :depth="row.category === '—' ? 3 : 1">{{
                    row.category
                  }}</NText></template
                >{{
                  basicFieldHint(row.basicInfoStatus, 'category_path')
                }}</NTooltip
              ></NDescriptionsItem
            >
            <NDescriptionsItem label="差评率"
              ><NTooltip :disabled="!row.basicInfoStatus"
                ><template #trigger
                  ><NText :depth="row.negativeReviewRate === null ? 3 : 1">{{
                    formatReviewRate(row.negativeReviewRate)
                  }}</NText></template
                >{{
                  basicFieldHint(row.basicInfoStatus, 'bad_comment_rate')
                }}</NTooltip
              ></NDescriptionsItem
            >
            <NDescriptionsItem label="首次上架日期"
              ><NTooltip :disabled="!row.basicInfoStatus"
                ><template #trigger
                  ><NText :depth="row.listedAt === null ? 3 : 1">{{
                    formatCandidateDate(row.listedAt)
                  }}</NText></template
                >{{
                  basicFieldHint(row.basicInfoStatus, 'first_on_shelf_date')
                }}</NTooltip
              ></NDescriptionsItem
            >
            <NDescriptionsItem label="商品资料采集状态"
              ><NText v-if="row.collectionStatus === 'unknown'" depth="3"
                >—</NText
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
                  ><NText depth="1">{{
                    row.shopName
                  }}</NText></NDescriptionsItem
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
                  ><NText
                    :depth="row.sourceContext.checkedAt === null ? 3 : 1"
                    >{{
                      formatCandidateTime(row.sourceContext.checkedAt)
                    }}</NText
                  ></NDescriptionsItem
                >
              </NDescriptions>
            </NCollapseItem>
          </NCollapse>
        </section>
      </div>
      <template #footer>
        <div class="candidate-detail__footer">
          <div class="candidate-detail__feedback" aria-live="polite">
            <NText v-if="basicFeedback" depth="3">{{ basicFeedback }}</NText>
            <NText
              v-if="
                service.basic &&
                capabilities.data.value?.basic_info_available === false
              "
              depth="3"
              >当前环境暂停更新</NText
            >
            <NText
              v-if="capabilities.isError.value || basicRun.isError.value"
              type="error"
              >{{
                capabilities.error.value?.message ??
                basicRun.error.value?.message
              }}</NText
            >
          </div>
          <div class="candidate-detail__actions">
            <AppButton @click="emit('close')">关闭</AppButton>
            <AppButton
              tone="secondary"
              :disabled="
                !row ||
                basicBusy ||
                (service.basic
                  ? capabilities.data.value?.basic_info_available !== true
                  : !service.available)
              "
              :loading="basicBusy"
              @click="updateBasic"
              >更新基础信息</AppButton
            >
            <NTooltip :disabled="service.available">
              <template #trigger>
                <span class="candidate-detail__action-trigger">
                  <AppButton
                    tone="primary"
                    :disabled="!row || busy || !service.available"
                    :loading="busy"
                    @click="act('collect')"
                    >采集资料</AppButton
                  >
                </span>
              </template>
              资料采集待接入
            </NTooltip>
          </div>
        </div>
      </template>
    </DetailDrawer>
  </NConfigProvider>
</template>

<style scoped>
.candidate-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
  color: var(--text-primary);
  font-size: var(--font-size-secondary);
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
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}
.candidate-detail__metadata {
  min-width: 0;
  max-width: 100%;
  font-size: var(--list-compact-font-size);
  font-weight: var(--font-weight-regular);
  overflow-wrap: anywhere;
}
.candidate-detail h3,
.candidate-detail__section-title {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.candidate-detail h3 {
  margin: 0 0 var(--space-2);
}
.candidate-detail__metric {
  font-size: var(--font-size-page-title);
  font-weight: var(--font-weight-semibold);
}
.candidate-detail__actions {
  justify-content: flex-end;
  flex: 0 0 auto;
  margin-left: auto;
  flex-wrap: nowrap;
}
.candidate-detail__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-3);
  width: 100%;
  min-width: 0;
  font-size: var(--list-compact-font-size);
}
.candidate-detail__feedback {
  display: flex;
  flex: 1 1 var(--field-width-sm);
  flex-direction: column;
  min-width: 0;
  gap: var(--space-1);
  overflow-wrap: anywhere;
}
.candidate-detail__feedback:empty {
  display: none;
}
.candidate-detail__action-trigger {
  display: inline-flex;
}
</style>
