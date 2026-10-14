<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NTooltip,
  NText,
  useMessage,
} from 'naive-ui'
import { useForm } from 'vee-validate'
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import ShopSelector from '@/entities/shop/ui/ShopSelector.vue'
import {
  AppDrawer,
  AppButton,
  AppInput,
  AppSelect,
  AppNumberInput,
  AppSwitch,
  AppCheckbox,
  AppRadio,
  AppTimePicker,
} from '@/shared/ui'
import { ErrorState } from '@/shared/components'
import {
  CREATOR_DEMO_OPTIONS,
  emptyStrategy,
  type ShortVideoConditions,
  type StrategyInput,
  type SelectionService,
  type SelectionStrategy,
  type SelectionExecutionSummary,
  type CategoryNode,
} from '../model/contracts'
import type { AppOption, AppOptionValue } from '@/shared/ui/types'
import type { SelectionCapabilitiesDto } from '../api/selection-read-api'
import { validateStrategy, realPriceErrors } from '../model/selection-rules'
import CategorySelector from './CategorySelector.vue'

const props = defineProps<{
  show: boolean
  strategy: SelectionStrategy | null
  service: SelectionService
  contextKey: string
  executionDisabledReason?: string | null
  capabilities?: SelectionCapabilitiesDto
}>()
const emit = defineEmits<{
  'update:show': [show: boolean]
  saved: [strategy: SelectionStrategy]
  retrieved: [execution?: SelectionExecutionSummary]
}>()
const message = useMessage()
const busy = ref(false)
const expanded = ref<string[]>(['short-video'])
const real = computed(() => !!props.service.manual)
const canSave = computed(
  () =>
    props.capabilities?.strategy_save_available ??
    props.service.strategySaveAvailable ??
    props.service.available,
)
const canSchedule = computed(
  () => props.service.scheduleAvailable ?? props.service.available,
)
let submission: { input: string; key: string } | null = null
const { values, errors, setFieldValue, setFieldError, resetForm, setErrors } =
  useForm<StrategyInput>({ initialValues: emptyStrategy() })
const conditions = computed(() => values.channels.shortVideo.conditions)
const periodPreview = useQuery({
  queryKey: computed(() => [
    'selection-period-preview',
    props.contextKey,
    conditions.value.period,
  ]),
  enabled: computed(() => props.show && !real.value && props.service.available),
  queryFn: () => props.service.previewPeriod(conditions.value.period),
  retry: false,
})
const refreshingShop = ref<string | null>(null)
const categories = useQuery({
  queryKey: computed(() => [
    'selection-categories',
    props.contextKey,
    values.shopId,
  ]),
  enabled: computed(
    () => props.show && !!values.shopId && values.channels.shortVideo.selected,
  ),
  queryFn: ({ queryKey }) =>
    props.service.categories(String(queryKey[2]), {
      refresh: refreshingShop.value === queryKey[2],
    }),
  retry: false,
  staleTime: 24 * 60 * 60 * 1000,
  gcTime: 24 * 60 * 60 * 1000,
})
watch(categories.data, (nodes) => {
  const saved = props.strategy?.requestScope
  if (
    !nodes ||
    !saved ||
    values.shopId !== props.strategy?.shopId ||
    conditions.value.categoryId !==
      [saved.industryId, ...saved.categoryIds].join('/')
  )
    return
  function match(tree: CategoryNode[]): string | null {
    for (const node of tree) {
      if (
        node.requestScope?.industryId === saved!.industryId &&
        JSON.stringify(node.requestScope.categoryIds) ===
          JSON.stringify(saved!.categoryIds)
      )
        return node.id
      const id = match(node.children ?? [])
      if (id) return id
    }
    return null
  }
  const id = match(nodes)
  if (id) setCondition('categoryId', id)
})
async function refreshCategories() {
  if (!values.shopId || categories.isFetching.value) return
  const shopId = values.shopId
  refreshingShop.value = shopId
  try {
    await categories.refetch({ cancelRefetch: false })
  } finally {
    if (refreshingShop.value === shopId) refreshingShop.value = null
  }
}
watch(
  () => props.show,
  (show) => {
    if (!show) return
    // JSON-shaped draft: detach nested Vue/Query objects before editing or passing to service.
    const draft = props.strategy
      ? (JSON.parse(JSON.stringify(props.strategy)) as StrategyInput)
      : emptyStrategy()
    if (real.value && !props.strategy) {
      draft.channels.shortVideo.conditions.period = '7d'
      draft.channels.shortVideo.conditions.rankFrom = 1
      draft.channels.shortVideo.conditions.rankTo = 10
      draft.enabled = false
    }
    resetForm({ values: draft })
    expanded.value = ['short-video']
  },
  { immediate: true },
)
function setCondition<K extends keyof ShortVideoConditions>(
  key: K,
  value: ShortVideoConditions[K],
) {
  const next = {
    ...conditions.value,
    [key]: value,
  }
  const priceWasInvalid =
    conditionError('priceAbove') || conditionError('priceBelow')
  setFieldValue('channels.shortVideo.conditions', next)
  if (
    real.value &&
    priceWasInvalid &&
    ['priceMode', 'priceAbove', 'priceBelow'].includes(key)
  ) {
    const priceErrors = realPriceErrors(next)
    for (const field of ['priceAbove', 'priceBelow'] as const)
      setFieldError(
        `channels.shortVideo.conditions.${field}`,
        priceErrors[field],
      )
  }
}
function conditionError(key: keyof ShortVideoConditions) {
  return errors.value[`channels.shortVideo.conditions.${key}`]
}
function changeShop(value: string | null) {
  setFieldValue('shopId', value)
  setCondition('categoryId', null)
}
const dailyTime = computed({
  get: () =>
    /^([01]\d|2[0-3]):[0-5]\d$/.test(values.dailyTime)
      ? dayjs(`2000-01-01T${values.dailyTime}:00`).valueOf()
      : null,
  set: (value: number | null) =>
    setFieldValue(
      'dailyTime',
      value === null ? '' : dayjs(value).format('HH:mm'),
    ),
})
const periodOptions = computed(
  () =>
    [
      { value: 'realtime', label: '实时' },
      { value: '1d', label: '近1天' },
      { value: '7d', label: '近7天' },
      { value: '30d', label: '近30天' },
    ].map((option) => ({
      ...option,
      disabled:
        real.value &&
        !(props.capabilities?.supported_periods ?? ['7d']).includes(
          option.value as ShortVideoConditions['period'],
        ),
    })) satisfies AppOption[],
)
function selectPeriod(value: AppOptionValue) {
  if (
    !periodOptions.value.some(
      (option) => option.value === value && !option.disabled,
    )
  )
    return
  setCondition('period', value as ShortVideoConditions['period'])
}
async function submit(saving: boolean) {
  if (busy.value) return
  if (saving && !canSave.value) {
    message.info(
      props.service.strategySaveAvailable
        ? '当前策略为只读，保存暂不可用'
        : '策略保存与定时执行待接入',
    )
    return
  }
  if (!saving && props.executionDisabledReason) {
    message.info(props.executionDisabledReason)
    return
  }
  const validation = validateStrategy(
    real.value && !saving ? { ...values, scheduled: false } : values,
    saving,
    real.value,
  )
  setErrors(validation)
  if (Object.keys(validation).length) {
    if (
      Object.keys(validation).some((key) =>
        key.startsWith('channels.shortVideo.conditions.'),
      ) &&
      !expanded.value.includes('short-video')
    )
      expanded.value.push('short-video')
    return
  }
  if (
    values.channels.shortVideo.selected &&
    (categories.isPending.value || categories.isError.value)
  ) {
    message.error('请先成功加载当前店铺类目')
    return
  }
  busy.value = true
  try {
    const draft = JSON.parse(JSON.stringify(values)) as StrategyInput
    if (!saving && real.value) {
      if (!props.service.manual) throw new Error('手动获取暂不可用')
      // Strategy name/status/schedule are editable draft metadata, not manual
      // execution parameters. They neither save nor change an uncertain receipt.
      const encoded = JSON.stringify({
        shopId: draft.shopId,
        channels: draft.channels,
        strategyId: props.strategy?.id,
        strategyVersion: props.strategy?.version,
      })
      if (submission?.input !== encoded)
        submission = { input: encoded, key: crypto.randomUUID() }
      // Keep the key on an uncertain HTTP failure; do not create another run.
      const receipt = await props.service.manual.submit(
        draft,
        submission.key,
        categories.data.value,
        props.strategy?.version
          ? { id: props.strategy.id, version: props.strategy.version }
          : undefined,
      )
      message.info(receipt.reused ? '已复用选品任务' : '已提交选品任务')
      submission = null
      emit('retrieved', receipt.execution)
      emit('update:show', false)
    } else if (saving) {
      const saved = real.value
        ? await props.service.saveStrategy(
            draft,
            props.strategy?.id,
            props.strategy?.version,
            categories.data.value,
          )
        : await props.service.saveStrategy(draft, props.strategy?.id)
      message.success(real.value ? '策略已保存' : '演示策略已保存')
      emit('saved', saved)
      emit('update:show', false)
    } else {
      const strategyId = props.strategy?.id
      const receipt = await props.service.retrieve(draft, strategyId)
      message.info(receipt.message)
      if (strategyId) emit('retrieved')
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '操作失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AppDrawer
    :show="show"
    :title="strategy ? '编辑选品策略' : '新建选品策略'"
    size="lg"
    @update:show="emit('update:show', $event)"
  >
    <NForm
      label-placement="left"
      label-align="right"
      :label-width="96"
      @submit.prevent="submit(true)"
    >
      <div class="strategy-pair">
        <NFormItem
          label="请求店铺"
          :validation-status="errors.shopId ? 'error' : undefined"
          :feedback="errors.shopId"
        >
          <ShopSelector
            :model-value="values.shopId"
            @update:model-value="changeShop"
          />
        </NFormItem>
        <NFormItem
          label="达人账号"
          :validation-status="errors.creatorId ? 'error' : undefined"
          :feedback="errors.creatorId"
        >
          <AppSelect
            :model-value="values.creatorId"
            :options="real ? [] : CREATOR_DEMO_OPTIONS"
            :disabled="real"
            :placeholder="real ? '达人账号待接入' : '请选择达人账号'"
            clearable
            @update:model-value="
              setFieldValue(
                'creatorId',
                $event === null ? null : String($event),
              )
            "
          />
        </NFormItem>
      </div>
      <NFormItem
        label="策略名称"
        :validation-status="errors.name ? 'error' : undefined"
        :feedback="errors.name"
      >
        <AppInput
          :model-value="values.name"
          aria-label="策略名称"
          @update:model-value="setFieldValue('name', $event)"
        />
      </NFormItem>
      <NFormItem
        label="渠道"
        label-placement="top"
        label-align="left"
        :validation-status="errors.channels ? 'error' : undefined"
        :feedback="errors.channels"
      >
        <NCollapse
          v-model:expanded-names="expanded"
          class="strategy-channels"
          display-directive="show"
        >
          <NCollapseItem name="short-video" title="短视频榜单">
            <template #header-extra>
              <span @click.stop
                ><AppCheckbox
                  :model-value="values.channels.shortVideo.selected"
                  aria-label="选择短视频榜单"
                  @update:model-value="
                    setFieldValue('channels.shortVideo.selected', $event)
                  "
              /></span>
            </template>
            <fieldset
              class="strategy-conditions"
              :disabled="!values.channels.shortVideo.selected"
            >
              <NFormItem label="类目">
                <div class="strategy-field">
                  <CategorySelector
                    :model-value="conditions.categoryId"
                    :nodes="categories.data.value ?? []"
                    :real="real"
                    :disabled="
                      !values.shopId || !values.channels.shortVideo.selected
                    "
                    :loading="
                      !!values.shopId &&
                      values.channels.shortVideo.selected &&
                      categories.isPending.value
                    "
                    @update:model-value="setCondition('categoryId', $event)"
                  />
                  <AppButton
                    tone="link"
                    size="small"
                    :disabled="
                      !values.shopId ||
                      categories.isFetching.value ||
                      !values.channels.shortVideo.selected
                    "
                    :loading="!!refreshingShop"
                    @click="refreshCategories"
                    >刷新类目</AppButton
                  >
                  <ErrorState
                    v-if="categories.isError.value"
                    title="类目加载失败"
                    description="请重试当前店铺类目"
                    retryable
                    @retry="refreshCategories"
                  />
                </div>
              </NFormItem>
              <NGrid :cols="12" x-gap="var(--space-3)">
                <NGi :span="7">
                  <NFormItem label="日期">
                    <div class="strategy-field">
                      <NTooltip>
                        <template #trigger
                          ><AppRadio
                            :model-value="conditions.period"
                            :options="periodOptions"
                            :disabled="!values.channels.shortVideo.selected"
                            aria-label="选品日期"
                            @update:model-value="selectPeriod"
                        /></template>
                        {{
                          real
                            ? '当前仅支持近7天；服务器按上海日期冻结截至昨日的7天，首查合法为空时最多回退一天，实际区间显示在结果中'
                            : (periodPreview.data.value?.rangeLabel ??
                              '区间暂不可用')
                        }}
                      </NTooltip>
                      <ErrorState
                        v-if="periodPreview.isError.value"
                        title="示例区间读取失败"
                        retryable
                        @retry="periodPreview.refetch()"
                      />
                    </div>
                  </NFormItem>
                </NGi>
                <NGi :span="5">
                  <NFormItem label="品牌">
                    <AppSelect
                      :model-value="conditions.brand"
                      :options="[
                        { label: '不限', value: 'all' },
                        {
                          label: '知名品牌',
                          value: 'known',
                          disabled:
                            real &&
                            !(
                              capabilities?.supported_brands ?? ['all']
                            ).includes('known'),
                        },
                        {
                          label: '非知名品牌',
                          value: 'unknown',
                          disabled:
                            real &&
                            !(
                              capabilities?.supported_brands ?? ['all']
                            ).includes('unknown'),
                        },
                      ]"
                      :disabled="!values.channels.shortVideo.selected"
                      @update:model-value="
                        setCondition(
                          'brand',
                          $event as ShortVideoConditions['brand'],
                        )
                      "
                    />
                  </NFormItem>
                </NGi>
              </NGrid>
              <NFormItem label="价格">
                <AppRadio
                  :model-value="conditions.priceMode"
                  :options="[
                    { label: '不限', value: 'all' },
                    {
                      label: '自定义',
                      value: 'custom',
                      disabled: real && !capabilities?.custom_price_available,
                    },
                  ]"
                  :disabled="!values.channels.shortVideo.selected"
                  @update:model-value="
                    setCondition(
                      'priceMode',
                      $event as ShortVideoConditions['priceMode'],
                    )
                  "
                />
              </NFormItem>
              <div
                v-if="conditions.priceMode === 'custom'"
                class="strategy-pair"
              >
                <NFormItem
                  :label="real ? '最低价格（元）' : '价格大于'"
                  :validation-status="
                    conditionError('priceAbove') ? 'error' : undefined
                  "
                  :feedback="conditionError('priceAbove')"
                >
                  <AppNumberInput
                    :model-value="conditions.priceAbove"
                    :min="0"
                    :disabled="!values.channels.shortVideo.selected"
                    @update:model-value="setCondition('priceAbove', $event)"
                  />
                </NFormItem>
                <NFormItem
                  :label="real ? '最高价格（元）' : '价格小于'"
                  :validation-status="
                    conditionError('priceBelow') ? 'error' : undefined
                  "
                  :feedback="conditionError('priceBelow')"
                >
                  <AppNumberInput
                    :model-value="conditions.priceBelow"
                    :min="0"
                    :disabled="!values.channels.shortVideo.selected"
                    @update:model-value="setCondition('priceBelow', $event)"
                  />
                </NFormItem>
              </div>
              <NFormItem label="首次上榜"
                ><AppSwitch
                  :model-value="conditions.firstListedOnly"
                  :disabled="
                    (real &&
                      capabilities?.first_listed_filter_available === false) ||
                    !values.channels.shortVideo.selected
                  "
                  @update:model-value="setCondition('firstListedOnly', $event)"
              /></NFormItem>
              <div class="strategy-pair">
                <NFormItem
                  label="起始排名"
                  :validation-status="
                    conditionError('rankFrom') ? 'error' : undefined
                  "
                  :feedback="conditionError('rankFrom')"
                >
                  <AppNumberInput
                    :model-value="conditions.rankFrom"
                    :min="1"
                    :max="real ? (capabilities?.max_rank ?? 200) : undefined"
                    :disabled="!values.channels.shortVideo.selected"
                    @update:model-value="setCondition('rankFrom', $event)"
                  />
                </NFormItem>
                <NFormItem
                  label="结束排名"
                  :validation-status="
                    conditionError('rankTo') ? 'error' : undefined
                  "
                  :feedback="conditionError('rankTo')"
                >
                  <AppNumberInput
                    :model-value="conditions.rankTo"
                    :min="1"
                    :max="real ? (capabilities?.max_rank ?? 200) : undefined"
                    :disabled="!values.channels.shortVideo.selected"
                    @update:model-value="setCondition('rankTo', $event)"
                  />
                </NFormItem>
              </div>
            </fieldset>
          </NCollapseItem>
          <NCollapseItem name="baiying" title="巨量百应">
            <template #header-extra>
              <span @click.stop
                ><AppCheckbox
                  :model-value="values.channels.baiying.selected"
                  :disabled="real"
                  aria-label="选择巨量百应"
                  @update:model-value="
                    setFieldValue('channels.baiying.selected', $event)
                  "
              /></span>
            </template>
          </NCollapseItem>
        </NCollapse>
      </NFormItem>
      <NFormItem label="定时执行">
        <NTooltip :disabled="canSchedule">
          <template #trigger
            ><AppSwitch
              :model-value="values.scheduled"
              @update:model-value="setFieldValue('scheduled', $event)"
          /></template>
          定时配置可保存；服务端调度待接入，不会创建或启用计划
        </NTooltip>
        <NText v-if="real && !canSchedule" depth="3">（调度待接入）</NText>
      </NFormItem>
      <div v-if="values.scheduled" class="strategy-pair">
        <NFormItem label="执行频率"
          ><AppSelect
            :model-value="values.scheduleKind"
            :options="[
              { label: '每 N 小时', value: 'hourly' },
              { label: '每日', value: 'daily' },
            ]"
            @update:model-value="
              setFieldValue(
                'scheduleKind',
                $event as StrategyInput['scheduleKind'],
              )
            "
        /></NFormItem>
        <NFormItem
          v-if="values.scheduleKind === 'hourly'"
          label="间隔（小时）"
          :validation-status="errors.hourlyInterval ? 'error' : undefined"
          :feedback="errors.hourlyInterval"
        >
          <AppNumberInput
            :model-value="values.hourlyInterval"
            :min="1"
            :max="2147483647"
            :precision="0"
            aria-label="每 N 小时"
            @update:model-value="setFieldValue('hourlyInterval', $event ?? 0)"
          />
        </NFormItem>
        <NFormItem
          v-if="values.scheduleKind === 'daily'"
          label="每日时间"
          :validation-status="errors.dailyTime ? 'error' : undefined"
          :feedback="errors.dailyTime"
        >
          <AppTimePicker
            v-model="dailyTime"
            :clearable="false"
            format="HH:mm"
          />
        </NFormItem>
      </div>
      <NFormItem label="策略状态">
        <NTooltip :disabled="canSave">
          <template #trigger
            ><AppSwitch
              :model-value="values.enabled"
              :disabled="!canSave"
              @update:model-value="setFieldValue('enabled', $event)"
          /></template>
          策略保存待接入，不能启用未保存的策略
        </NTooltip>
      </NFormItem>
    </NForm>
    <template #footer
      ><div class="strategy-actions">
        <AppButton :disabled="busy" @click="emit('update:show', false)"
          >取消</AppButton
        >
        <NTooltip :disabled="!executionDisabledReason">
          <template #trigger
            ><AppButton
              tone="primary"
              :loading="busy"
              :disabled="!!executionDisabledReason"
              @click="submit(false)"
              >立即获取</AppButton
            ></template
          >
          {{ executionDisabledReason }}
        </NTooltip>
        <NTooltip :disabled="canSave">
          <template #trigger
            ><AppButton
              tone="primary"
              :loading="busy"
              :disabled="!canSave"
              @click="submit(true)"
              >保存策略</AppButton
            ></template
          >
          策略保存待接入
        </NTooltip>
      </div></template
    >
  </AppDrawer>
</template>

<style scoped>
.strategy-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.strategy-field,
.strategy-channels {
  width: 100%;
  min-width: 0;
}
.strategy-conditions {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.strategy-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
