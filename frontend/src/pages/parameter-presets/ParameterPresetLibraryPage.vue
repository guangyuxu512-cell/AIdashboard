<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

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
import { AppButton, AppInput, AppSelect } from '@/shared/ui'

const management = useParameterPresetManagement()
const route = useRoute()
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
const filterApplicationOptions = computed(() =>
  management.applicationOptions.value.map((application) => ({
    label: application.app_name,
    value: application.app_id,
  })),
)
const schemaDialogOpen = computed({
  get: () => Boolean(schemaDialogApplication.value),
  set: (show: boolean) => {
    if (!show) schemaDialogApplication.value = null
  },
})

watch(
  () => route.query.app_id,
  (appId) => {
    const value = typeof appId === 'string' ? appId : null
    if (management.selectedAppIdDraft.value === value) return
    management.selectedAppIdDraft.value = value
    management.query()
  },
  { immediate: true },
)

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
      <AppInput
        v-model="management.searchDraft.value"
        width="lg"
        clearable
        placeholder="搜索配置名称"
        @keyup.enter="management.query"
      />
      <AppSelect
        v-model="management.selectedAppIdDraft.value"
        :options="filterApplicationOptions"
        :loading="management.applicationsLoading.value"
        clearable
        placeholder="全部应用"
      />
      <template #actions>
        <AppButton @click="management.reset">重置</AppButton>
        <AppButton tone="primary" @click="management.query">查询</AppButton>
      </template>
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate"
          >+ 新建配置</AppButton
        >
      </template>
    </FilterBar>

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
</style>
