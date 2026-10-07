<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { useForm } from 'vee-validate'
import { useQuery } from '@tanstack/vue-query'
import ShopSelector from '@/entities/shop/ui/ShopSelector.vue'
import {
  AppDrawer,
  AppButton,
  AppInput,
  AppSelect,
  AppNumberInput,
  AppSwitch,
} from '@/shared/ui'
import { ContextSwitchBar, ErrorState } from '@/shared/components'
import {
  CHANNEL_OPTIONS,
  CREATOR_DEMO_OPTIONS,
  emptyStrategy,
  type StrategyInput,
  type SelectionService,
  type SelectionStrategy,
} from '../model/contracts'
import { validateStrategy } from '../model/selection-rules'
import CategorySelector from './CategorySelector.vue'

const props = defineProps<{
  show: boolean
  strategy: SelectionStrategy | null
  service: SelectionService
  contextKey: string
}>()
const emit = defineEmits<{ 'update:show': [show: boolean]; saved: [] }>()
const message = useMessage()
const busy = ref(false)
const { values, errors, setFieldValue, resetForm, setErrors } =
  useForm<StrategyInput>({ initialValues: emptyStrategy() })
const categories = useQuery({
  queryKey: computed(() => [
    'selection-categories',
    props.contextKey,
    values.shopId,
  ]),
  enabled: computed(() => props.show && !!values.shopId),
  queryFn: ({ queryKey }) => props.service.categories(String(queryKey[2])),
  retry: false,
})
watch(
  () => props.show,
  (show) => {
    if (show)
      resetForm({
        values: props.strategy ? { ...props.strategy } : emptyStrategy(),
      })
  },
  { immediate: true },
)
function changeShop(value: string | null) {
  setFieldValue('shopId', value)
  setFieldValue('categoryId', null)
}
const periodItems = [
  { key: 'realtime', label: '实时' },
  { key: '1d', label: '近1天' },
  { key: '7d', label: '近7天' },
  { key: '30d', label: '近30天' },
  { key: 'more', label: '更多' },
]
function selectPeriod(value: string) {
  if (value === 'more') {
    message.info('更多日期选项尚未确认')
    return
  }
  setFieldValue('period', value as StrategyInput['period'])
}
async function submit(saving: boolean) {
  if (busy.value) return
  const validation = validateStrategy(values, saving)
  setErrors(validation)
  if (Object.keys(validation).length) return
  if (
    values.channel === 'short-video' &&
    (categories.isPending.value || categories.isError.value)
  ) {
    message.error('请先成功加载当前店铺类目')
    return
  }
  busy.value = true
  try {
    if (saving) {
      await props.service.saveStrategy(
        structuredClone({ ...values }),
        props.strategy?.id,
      )
      message.success('演示策略已保存')
      emit('saved')
      emit('update:show', false)
    } else {
      const receipt = await props.service.retrieve(
        structuredClone({ ...values }),
      )
      message.info(receipt.message)
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
    <NForm label-placement="top" @submit.prevent="submit(true)">
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
      <NFormItem label="渠道">
        <ContextSwitchBar
          label="选品渠道"
          appearance="bare"
          :items="
            CHANNEL_OPTIONS.map((option) => ({
              key: option.value,
              label: option.label,
            }))
          "
          :active-key="values.channel"
          @select="setFieldValue('channel', $event as StrategyInput['channel'])"
        />
      </NFormItem>
      <template v-if="values.channel === 'short-video'">
        <NFormItem label="类目">
          <div class="strategy-field">
            <CategorySelector
              :model-value="values.categoryId"
              :nodes="categories.data.value ?? []"
              :disabled="!values.shopId"
              :loading="!!values.shopId && categories.isPending.value"
              @update:model-value="setFieldValue('categoryId', $event)"
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
        <NFormItem label="日期">
          <ContextSwitchBar
            label="榜单日期"
            appearance="bare"
            :items="periodItems"
            :active-key="values.period"
            @select="selectPeriod"
          />
        </NFormItem>
        <NFormItem label="品牌">
          <AppSelect
            :model-value="values.brand"
            :options="[
              { label: '不限', value: 'all' },
              { label: '知名品牌', value: 'known' },
              { label: '非知名品牌', value: 'unknown' },
            ]"
            @update:model-value="
              setFieldValue('brand', $event as StrategyInput['brand'])
            "
          />
        </NFormItem>
        <NFormItem label="价格">
          <ContextSwitchBar
            label="价格条件"
            appearance="bare"
            :items="[
              { key: 'all', label: '不限' },
              { key: 'custom', label: '自定义' },
            ]"
            :active-key="values.priceMode"
            @select="
              setFieldValue('priceMode', $event as StrategyInput['priceMode'])
            "
          />
        </NFormItem>
        <div v-if="values.priceMode === 'custom'" class="strategy-pair">
          <NFormItem
            label="价格大于"
            :validation-status="errors.priceAbove ? 'error' : undefined"
            :feedback="errors.priceAbove"
          >
            <AppNumberInput
              :model-value="values.priceAbove"
              :min="0"
              @update:model-value="setFieldValue('priceAbove', $event)"
            />
          </NFormItem>
          <NFormItem
            label="价格小于"
            :validation-status="errors.priceBelow ? 'error' : undefined"
            :feedback="errors.priceBelow"
          >
            <AppNumberInput
              :model-value="values.priceBelow"
              :min="0"
              @update:model-value="setFieldValue('priceBelow', $event)"
            />
          </NFormItem>
        </div>
        <NFormItem label="首次上榜">
          <AppSwitch
            :model-value="values.firstListedOnly"
            @update:model-value="setFieldValue('firstListedOnly', $event)"
          />
        </NFormItem>
        <div class="strategy-pair">
          <NFormItem
            label="起始排名"
            :validation-status="errors.rankFrom ? 'error' : undefined"
            :feedback="errors.rankFrom"
          >
            <AppNumberInput
              :model-value="values.rankFrom"
              :min="1"
              @update:model-value="setFieldValue('rankFrom', $event)"
            />
          </NFormItem>
          <NFormItem
            label="结束排名"
            :validation-status="errors.rankTo ? 'error' : undefined"
            :feedback="errors.rankTo"
          >
            <AppNumberInput
              :model-value="values.rankTo"
              :min="1"
              @update:model-value="setFieldValue('rankTo', $event)"
            />
          </NFormItem>
        </div>
      </template>
      <NFormItem label="定时执行">
        <AppSwitch
          :model-value="values.scheduled"
          @update:model-value="setFieldValue('scheduled', $event)"
        />
      </NFormItem>
      <div v-if="values.scheduled" class="strategy-pair">
        <NFormItem label="执行频率">
          <AppSelect
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
          />
        </NFormItem>
        <NFormItem
          v-if="values.scheduleKind === 'daily'"
          label="每日时间"
          :validation-status="errors.dailyTime ? 'error' : undefined"
          :feedback="errors.dailyTime"
        >
          <AppInput
            :model-value="values.dailyTime"
            placeholder="HH:mm"
            aria-label="每日时间"
            @update:model-value="setFieldValue('dailyTime', $event)"
          />
        </NFormItem>
      </div>
      <NFormItem label="策略状态">
        <AppSwitch
          :model-value="values.enabled"
          @update:model-value="setFieldValue('enabled', $event)"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <div class="strategy-actions">
        <AppButton :disabled="busy" @click="emit('update:show', false)"
          >取消</AppButton
        >
        <AppButton :loading="busy" @click="submit(false)">立即获取</AppButton>
        <AppButton tone="primary" :loading="busy" @click="submit(true)"
          >保存策略</AppButton
        >
      </div>
    </template>
  </AppDrawer>
</template>

<style scoped>
.strategy-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.strategy-field {
  width: 100%;
  min-width: 0;
}
.strategy-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
