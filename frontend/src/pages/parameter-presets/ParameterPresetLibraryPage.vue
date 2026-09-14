<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  AutomationParameterPresetManagerDialog,
  type AutomationInputSchemaDto,
  useAutomationApplicationConfigQuery,
  type AutomationParameterPresetDto,
  type YingdaoApplicationOptionDto,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import {
  ParameterPresetListTable,
  ParameterPresetDeleteDialog,
  useParameterPresetManagement,
} from '@/features/parameter-preset-management'
import YingdaoApplicationConfigDialog from '@/features/device-management/ui/YingdaoApplicationConfigDialog.vue'
import { getErrorMessage } from '@/shared/api'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

const management = useParameterPresetManagement()
const route = useRoute()
const router = useRouter()
const autoSearch = useAutoSearch(pushCurrentFilters)
const schemaDialogApplication = ref<ProviderApplicationViewModel | null>(null)
const schemaDialogSchema = ref<AutomationInputSchemaDto>({ fields: [] })
const managerDialog = ref<InstanceType<
  typeof AutomationParameterPresetManagerDialog
> | null>(null)
const configQuery = useAutomationApplicationConfigQuery(
  () => management.editorAppId.value,
  // Existing presets read their persisted schema from the preset API.  Only a
  // brand-new preset needs the mutable application template as its seed.
  () => management.editorVisible.value && !management.editorPresetId.value,
)
const editorSchema = computed(
  () => configQuery.data.value?.input_schema ?? { fields: [] },
)
const editorSchemaLoading = computed(
  () =>
    management.editorVisible.value &&
    !management.editorPresetId.value &&
    configQuery.isPending.value,
)
const editorSchemaError = computed(() =>
  management.editorPresetId.value || !configQuery.error.value
    ? null
    : getErrorMessage(configQuery.error.value),
)
const filterApplicationOptions = computed(() => {
  const nameCounts = new Map<string, number>()
  for (const application of management.applicationOptions.value) {
    nameCounts.set(
      application.app_name,
      (nameCounts.get(application.app_name) ?? 0) + 1,
    )
  }
  return management.applicationOptions.value.map((application) => ({
    label:
      (nameCounts.get(application.app_name) ?? 0) > 1
        ? `${application.app_name} · ${application.app_id}`
        : application.app_name,
    value: application.app_id,
  }))
})
const emptySelectedApplication = computed(
  () =>
    Boolean(management.selectedAppIdDraft.value) &&
    management.applicationsLoaded.value &&
    !management.invalidSelectedApp.value &&
    !management.listLoading.value &&
    !management.listError.value &&
    management.total.value === 0,
)
const schemaDialogOpen = computed({
  get: () => Boolean(schemaDialogApplication.value),
  set: (show: boolean) => {
    if (!show) schemaDialogApplication.value = null
  },
})

function queryString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

watch(
  () => [route.query.device_id, route.query.app_id, route.query.q] as const,
  ([deviceId, appId, query]) => {
    management.selectedDeviceIdDraft.value = queryString(deviceId)
    management.selectedAppIdDraft.value = queryString(appId)
    management.searchDraft.value = queryString(query) ?? ''
    management.query()
  },
  { immediate: true },
)

function pushCurrentFilters(): void {
  const query = {
    ...(management.selectedDeviceIdDraft.value
      ? { device_id: management.selectedDeviceIdDraft.value }
      : {}),
    ...(management.selectedAppIdDraft.value
      ? { app_id: management.selectedAppIdDraft.value }
      : {}),
    ...(management.searchDraft.value.trim()
      ? { q: management.searchDraft.value.trim() }
      : {}),
  }
  if (
    queryString(route.query.device_id) === (query.device_id ?? null) &&
    queryString(route.query.app_id) === (query.app_id ?? null) &&
    queryString(route.query.q) === (query.q ?? null)
  ) {
    management.query()
    return
  }
  void router.push({ path: route.path, query })
}

function selectDevice(value: string | number | null): void {
  autoSearch.cancel()
  management.selectedDeviceIdDraft.value = value === null ? null : String(value)
  management.selectedAppIdDraft.value = null
  pushCurrentFilters()
}

function selectApplication(value: string | number | null): void {
  autoSearch.cancel()
  management.selectedAppIdDraft.value = value === null ? null : String(value)
  pushCurrentFilters()
}

function resetFilters(): void {
  autoSearch.cancel()
  management.searchDraft.value = ''
  management.selectedDeviceIdDraft.value = null
  management.selectedAppIdDraft.value = null
  void router.push({ path: route.path })
}

function openPreset(preset: AutomationParameterPresetDto): void {
  management.openPreset(preset)
}

function openSchemaConfiguration(
  application: YingdaoApplicationOptionDto,
  schema: AutomationInputSchemaDto,
): void {
  schemaDialogApplication.value = {
    appId: application.app_id,
    appName: application.app_name,
    versionId: null,
  }
  schemaDialogSchema.value = schema
}

function applyPresetSchema(schema: AutomationInputSchemaDto): void {
  managerDialog.value?.applyInputSchema(schema)
}
</script>

<template>
  <div class="page-container parameter-preset-library-page">
    <FilterBar>
      <AppSelect
        :model-value="management.selectedDeviceIdDraft.value"
        :options="management.deviceOptions.value"
        :loading="management.deviceOptionsLoading.value"
        width="md"
        clearable
        filterable
        placeholder="全部设备"
        @update:model-value="selectDevice"
      />
      <AppSelect
        :model-value="management.selectedAppIdDraft.value"
        :options="filterApplicationOptions"
        :loading="management.applicationsLoading.value"
        width="md"
        clearable
        filterable
        placeholder="全部应用"
        @update:model-value="selectApplication"
      />
      <AppInput
        v-model="management.searchDraft.value"
        width="lg"
        clearable
        placeholder="搜索配置名称"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(management.searchDraft.value)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
      <template #actions>
        <AppButton @click="resetFilters">重置</AppButton>
      </template>
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate"
          >+ 新建配置</AppButton
        >
      </template>
    </FilterBar>

    <p
      v-if="management.deviceOptionsError.value"
      class="parameter-preset-library-page__error"
      role="alert"
    >
      设备列表读取失败：{{ management.deviceOptionsError.value }}
    </p>

    <p
      v-if="management.applicationsError.value"
      class="parameter-preset-library-page__error"
    >
      应用列表读取失败：{{ management.applicationsError.value }}
      <AppButton tone="text" @click="() => management.retryApplications()"
        >重试</AppButton
      >
    </p>
    <p
      v-if="
        management.selectedDeviceCapabilityState.value &&
        management.selectedDeviceCapabilityState.value.kind !== 'ready'
      "
      class="parameter-preset-library-page__notice"
      :class="{
        'parameter-preset-library-page__error':
          management.selectedDeviceCapabilityState.value.kind === 'error',
      }"
    >
      {{ management.selectedDeviceCapabilityState.value.message }}
    </p>
    <p
      v-if="management.invalidSelectedApp.value"
      class="parameter-preset-library-page__error"
      role="alert"
    >
      当前应用标识无效或当前团队不可访问；系统不会按应用名称匹配。请从能力页进入或重新选择应用。
    </p>
    <div
      v-if="emptySelectedApplication"
      class="parameter-preset-library-page__empty-action"
    >
      <span>该应用暂无配置</span>
      <AppButton tone="primary" @click="management.openCreate">
        为此应用新建配置
      </AppButton>
    </div>
    <p
      v-if="management.copyError.value"
      class="parameter-preset-library-page__error"
      role="alert"
    >
      复制预设失败：{{ management.copyError.value }}
    </p>
    <p
      v-if="management.removeError.value"
      class="parameter-preset-library-page__error"
      role="alert"
    >
      删除配置失败：{{ management.removeError.value }}
    </p>

    <ManagementListSection>
      <ParameterPresetListTable
        :rows="management.rows.value"
        :app-name-by-id="management.applicationNameById.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        @edit="openPreset"
        @copy="management.copyAndOpen"
        @remove="management.requestRemove"
        @retry="management.retryList"
      />
      <PaginationBar
        :page="management.page.value"
        :page-size="management.pageSize.value"
        :item-count="management.total.value"
        @update:page="management.setPage"
        @update:page-size="management.setPageSize"
      />
    </ManagementListSection>

    <AutomationParameterPresetManagerDialog
      ref="managerDialog"
      :show="management.editorVisible.value"
      :app-id="management.editorAppId.value"
      :schema="editorSchema"
      :application-options="management.applicationOptions.value"
      :application-options-loading="management.applicationsLoading.value"
      :initial-preset-id="management.editorPresetId.value"
      :schema-loading="editorSchemaLoading"
      :schema-error="editorSchemaError"
      allow-schema-configuration
      @update:show="(show) => (show ? undefined : management.closeEditor())"
      @update:app-id="(appId) => (management.editorAppId.value = appId)"
      @saved="management.handleSaved"
      @configure-schema="openSchemaConfiguration"
    />

    <YingdaoApplicationConfigDialog
      v-model:show="schemaDialogOpen"
      :application="schemaDialogApplication"
      :preset-schema="schemaDialogSchema"
      @confirm-preset-schema="applyPresetSchema"
    />

    <ParameterPresetDeleteDialog
      v-model:show="management.removeVisible.value"
      :preset="management.removePreset.value"
      :submitting="management.removeSubmitting.value"
      @confirm="management.confirmRemove"
    />
  </div>
</template>

<style scoped>
.parameter-preset-library-page {
  height: 100%;
  min-height: 0;
}

.parameter-preset-library-page__error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  color: var(--color-error);
}

.parameter-preset-library-page__notice,
.parameter-preset-library-page__empty-action {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
}

.parameter-preset-library-page__empty-action {
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
</style>
