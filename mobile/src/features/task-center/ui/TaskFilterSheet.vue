<script setup lang="ts">
import {
  Button as VanButton,
  Calendar as VanCalendar,
  Cell as VanCell,
  Empty as VanEmpty,
  Field as VanField,
  List as VanList,
  Loading as VanLoading,
  NavBar as VanNavBar,
  Picker as VanPicker,
  Popup as VanPopup,
  Search as VanSearch,
} from 'vant'
import { computed, nextTick, ref, watch } from 'vue'

import { useDeviceListQuery } from '@/entities/device'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

import {
  createDefaultTaskFilterDraft,
  formatTaskDateFilterLabel,
  TASK_DATE_PRESET_OPTIONS,
  type TaskDatePreset,
  type TaskFilterDraft,
} from '../model/task-filter'

const props = defineProps<{
  modelValue: boolean
  filters: TaskFilterDraft
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  apply: [filters: TaskFilterDraft]
}>()

const draft = ref<TaskFilterDraft>(createDefaultTaskFilterDraft())
const showDevices = ref(false)
const showDatePresets = ref(false)
const showCalendar = ref(false)
const deviceQuery = useDeviceListQuery(showDevices)
const datePresetColumns = TASK_DATE_PRESET_OPTIONS.map((option) => ({
  ...option,
}))

const devices = computed(() => {
  const seen = new Set<string>()
  return (deviceQuery.data.value?.pages ?? [])
    .flatMap((page) => page.items)
    .filter((device) => {
      if (seen.has(device.device_id)) return false
      seen.add(device.device_id)
      return true
    })
})

const dateLabel = computed(() => formatTaskDateFilterLabel(draft.value))
const deviceErrorKind = computed(() =>
  classifyInfiniteQueryError({
    hasSuccessfulData: deviceQuery.data.value !== undefined,
    isError: deviceQuery.isError.value,
    isFetchNextPageError: deviceQuery.isFetchNextPageError.value,
  }),
)

watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) return
    draft.value = {
      ...props.filters,
      dateRange: [props.filters.dateRange[0], props.filters.dateRange[1]],
    }
  },
)

async function loadMoreDevices(): Promise<void> {
  if (
    !deviceQuery.hasNextPage.value ||
    deviceQuery.isFetchingNextPage.value ||
    deviceErrorKind.value === 'next-page'
  ) {
    return
  }
  await deviceQuery.fetchNextPage()
}

async function retryMoreDevices(): Promise<void> {
  if (!deviceQuery.hasNextPage.value || deviceQuery.isFetchingNextPage.value) {
    return
  }
  await deviceQuery.fetchNextPage()
}

function chooseDevice(deviceId: string, deviceName: string): void {
  draft.value.deviceId = deviceId
  draft.value.deviceName = deviceName
  showDevices.value = false
}

function confirmDate(value: Date | Date[]): void {
  if (!Array.isArray(value) || value.length < 2) return
  draft.value.datePreset = 'custom'
  draft.value.dateRange = [value[0], value[1]]
  showCalendar.value = false
}

interface DatePresetConfirmPayload {
  selectedValues: Array<string | number>
}

async function confirmDatePreset({
  selectedValues,
}: DatePresetConfirmPayload): Promise<void> {
  const selected = selectedValues[0]
  const preset = TASK_DATE_PRESET_OPTIONS.find(
    (option) => option.value === selected,
  )?.value
  if (!preset) return

  showDatePresets.value = false
  if (preset === 'custom') {
    await nextTick()
    showCalendar.value = true
    return
  }
  draft.value.datePreset = preset as TaskDatePreset
}

function reset(): void {
  draft.value = createDefaultTaskFilterDraft()
}

function apply(): void {
  emit('apply', {
    ...draft.value,
    dateRange: [draft.value.dateRange[0], draft.value.dateRange[1]],
  })
  emit('update:modelValue', false)
}
</script>

<template>
  <VanPopup
    :show="modelValue"
    position="bottom"
    round
    class="task-filter-sheet"
    @update:show="emit('update:modelValue', $event)"
  >
    <VanNavBar title="筛选任务" />
    <div class="task-filter-sheet__body">
      <VanSearch
        v-model="draft.search"
        placeholder="搜索任务"
        :maxlength="500"
      />
      <VanField
        label="设备"
        :model-value="draft.deviceName || '全部设备'"
        readonly
        is-link
        data-testid="device-filter"
        @click="showDevices = true"
      />
      <VanField
        label="日期"
        :model-value="dateLabel"
        readonly
        is-link
        data-testid="date-filter"
        @click="showDatePresets = true"
      />
    </div>
    <div class="task-filter-sheet__actions">
      <VanButton block @click="reset">重置</VanButton>
      <VanButton type="primary" block data-testid="apply-filter" @click="apply">
        应用筛选
      </VanButton>
    </div>
  </VanPopup>

  <VanPopup
    v-model:show="showDevices"
    position="bottom"
    round
    class="task-filter-sheet__device-popup"
  >
    <VanNavBar title="选择设备">
      <template #left>
        <button
          type="button"
          class="task-filter-sheet__device-back"
          aria-label="返回"
          @click="showDevices = false"
        >
          返回
        </button>
      </template>
    </VanNavBar>
    <VanCell title="全部设备" clickable @click="chooseDevice('', '')" />
    <VanList
      v-if="
        deviceQuery.data.value !== undefined && deviceErrorKind !== 'initial'
      "
      :loading="deviceQuery.isFetchingNextPage.value"
      :finished="
        !deviceQuery.hasNextPage.value || deviceErrorKind === 'next-page'
      "
      :finished-text="deviceErrorKind === 'next-page' ? '' : '设备已全部加载'"
      @load="loadMoreDevices"
    >
      <VanCell
        v-for="device in devices"
        :key="device.device_id"
        :title="device.display_name"
        clickable
        @click="chooseDevice(device.device_id, device.display_name)"
      />
      <div
        v-if="deviceErrorKind === 'next-page'"
        class="task-filter-sheet__next-error"
        data-testid="device-next-page-error"
      >
        <span>加载失败</span>
        <VanButton block @click="retryMoreDevices">重试</VanButton>
      </div>
    </VanList>
    <div v-if="deviceQuery.isLoading.value" class="task-filter-sheet__loading">
      <VanLoading>加载设备中</VanLoading>
    </div>
    <VanEmpty
      v-else-if="deviceErrorKind === 'initial'"
      image="error"
      description="加载失败"
    >
      <VanButton type="primary" @click="deviceQuery.refetch()">
        重试
      </VanButton>
    </VanEmpty>
  </VanPopup>

  <VanPopup
    v-model:show="showDatePresets"
    position="bottom"
    round
    class="task-filter-sheet__preset-popup"
  >
    <VanPicker
      title="选择日期范围"
      :columns="datePresetColumns"
      :model-value="[draft.datePreset]"
      @confirm="confirmDatePreset"
      @cancel="showDatePresets = false"
    />
  </VanPopup>

  <VanCalendar
    v-model:show="showCalendar"
    class="task-filter-sheet__calendar"
    type="range"
    switch-mode="month"
    :default-date="[draft.dateRange[0], draft.dateRange[1]]"
    :max-date="new Date()"
    @confirm="confirmDate"
  />
</template>

<style scoped>
.task-filter-sheet {
  min-height: var(--overlay-height-medium);
  padding-right: var(--safe-area-right);
  padding-bottom: calc(var(--space-4) + var(--safe-area-bottom));
  padding-left: var(--safe-area-left);
  background: var(--bg-surface);
}

.task-filter-sheet__body {
  padding: var(--space-3) 0;
}

.task-filter-sheet__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  padding: var(--space-4);
}

.task-filter-sheet__device-popup {
  min-height: var(--overlay-height-large);
  max-height: var(--overlay-height-max);
  overflow-y: auto;
  padding-right: var(--safe-area-right);
  padding-bottom: var(--safe-area-bottom);
  padding-left: var(--safe-area-left);
  background: var(--bg-surface);
}

.task-filter-sheet__preset-popup {
  padding-right: var(--safe-area-right);
  padding-bottom: var(--safe-area-bottom);
  padding-left: var(--safe-area-left);
}

.task-filter-sheet__loading {
  display: grid;
  min-height: var(--layout-inline-state-min-height);
  place-items: center;
}

.task-filter-sheet__device-back {
  display: inline-flex;
  min-width: var(--touch-target-min);
  min-height: var(--touch-target-min);
  padding: 0 var(--space-2);
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  font: inherit;
  background: transparent;
  border: 0;
  border-radius: var(--radius-control);
}

:global(.task-filter-sheet__calendar) {
  padding-right: var(--safe-area-right);
  padding-left: var(--safe-area-left);
}

.task-filter-sheet__next-error {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
}
</style>
