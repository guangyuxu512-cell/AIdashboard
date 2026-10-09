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
} from '../model/contracts'
import type { AppOption, AppOptionValue } from '@/shared/ui/types'
import { validateStrategy } from '../model/selection-rules'
import CategorySelector from './CategorySelector.vue'

const props = defineProps<{
  show: boolean
  strategy: SelectionStrategy | null
  service: SelectionService
  contextKey: string
}>()
const emit = defineEmits<{
  'update:show': [show: boolean]
  saved: []
  retrieved: []
}>()
const message = useMessage()
const busy = ref(false)
const expanded = ref<string[]>(['short-video'])
const { values, errors, setFieldValue, resetForm, setErrors } =
  useForm<StrategyInput>({ initialValues: emptyStrategy() })
const conditions = computed(() => values.channels.shortVideo.conditions)
const periodPreview = useQuery({
  queryKey: computed(() => [
    'selection-period-preview',
    props.contextKey,
    conditions.value.period,
  ]),
  enabled: computed(() => props.show && props.service.available),
  queryFn: () => props.service.previewPeriod(conditions.value.period),
  retry: false,
})
const categories = useQuery({
  queryKey: computed(() => [
    'selection-categories',
    props.contextKey,
    values.shopId,
  ]),
  enabled: computed(
    () => props.show && !!values.shopId && values.channels.shortVideo.selected,
  ),
  queryFn: ({ queryKey }) => props.service.categories(String(queryKey[2])),
  retry: false,
})
watch(
  () => props.show,
  (show) => {
    if (!show) return
    // JSON-shaped draft: detach nested Vue/Query objects before editing or passing to service.
    resetForm({
      values: props.strategy
        ? (JSON.parse(JSON.stringify(props.strategy)) as StrategyInput)
        : emptyStrategy(),
    })
    expanded.value = ['short-video']
  },
  { immediate: true },
)
function setCondition<K extends keyof ShortVideoConditions>(
  key: K,
  value: ShortVideoConditions[K],
) {
  setFieldValue('channels.shortVideo.conditions', {
    ...conditions.value,
    [key]: value,
  })
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
const periodOptions = [
  { value: 'realtime', label: '实时' },
  { value: '1d', label: '近1天' },
  { value: '7d', label: '近7天' },
  { value: '30d', label: '近30天' },
] satisfies AppOption[]
function selectPeriod(value: AppOptionValue) {
  if (!periodOptions.some((option) => option.value === value)) return
  setCondition('period', value as ShortVideoConditions['period'])
}
async function submit(saving: boolean) {
  if (busy.value) return
  const validation = validateStrategy(values, saving)
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
    if (saving) {
      await props.service.saveStrategy(draft, props.strategy?.id)
      message.success('演示策略已保存')
      emit('saved')
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
            :options="CREATOR_DEMO_OPTIONS"
            placeholder="请选择达人账号"
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
                  <ErrorState
                    v-if="categories.isError.value"
                    title="类目加载失败"
                    description="请重试当前店铺类目"
                    retryable
                    @retry="categories.refetch()"
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
                          periodPreview.data.value?.rangeLabel ?? '区间暂不可用'
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
                        { label: '知名品牌', value: 'known' },
                        { label: '非知名品牌', value: 'unknown' },
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
                    { label: '自定义', value: 'custom' },
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
                  label="价格大于"
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
                  label="价格小于"
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
                  :disabled="!values.channels.shortVideo.selected"
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
                  aria-label="选择巨量百应"
                  @update:model-value="
                    setFieldValue('channels.baiying.selected', $event)
                  "
              /></span>
            </template>
          </NCollapseItem>
        </NCollapse>
      </NFormItem>
      <NFormItem label="定时执行"
        ><AppSwitch
          :model-value="values.scheduled"
          @update:model-value="setFieldValue('scheduled', $event)"
      /></NFormItem>
      <div v-if="values.scheduled" class="strategy-pair">
        <NFormItem label="执行频率"
          ><AppSelect
            :model-value="values.scheduleKind"
            :options="[
              { label: '每小时', value: 'hourly' },
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
      <NFormItem label="策略状态"
        ><AppSwitch
          :model-value="values.enabled"
          @update:model-value="setFieldValue('enabled', $event)"
      /></NFormItem>
    </NForm>
    <template #footer
      ><div class="strategy-actions">
        <AppButton :disabled="busy" @click="emit('update:show', false)"
          >取消</AppButton
        >
        <AppButton tone="primary" :loading="busy" @click="submit(false)"
          >立即获取</AppButton
        >
        <AppButton tone="primary" :loading="busy" @click="submit(true)"
          >保存策略</AppButton
        >
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
