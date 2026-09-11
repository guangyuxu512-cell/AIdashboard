<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  AutomationParameterPresetManagerDialog,
  useAutomationApplicationConfigQuery,
  type AutomationParameterPresetDto,
  type YingdaoApplicationOptionDto,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import {
  ParameterPresetListTable,
  useParameterPresetManagement,
} from '@/features/parameter-preset-management'
import YingdaoApplicationConfigDialog from '@/features/device-management/ui/YingdaoApplicationConfigDialog.vue'
import { getErrorMessage } from '@/shared/api'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'

const management = useParameterPresetManagement()
const schemaDialogApplication = ref<ProviderApplicationViewModel | null>(null)
const configQuery = useAutomationApplicationConfigQuery(
  () => management.editorAppId.value,
  () => management.editorVisible.value,
)
const editorSchema = computed(
  () => configQuery.data.value?.input_schema ?? { fields: [] },
)
const editorSchemaError = computed(() =>
  configQuery.error.value ? getErrorMessage(configQuery.error.value) : null,
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

function openPreset(preset: AutomationParameterPresetDto): void {
  management.openPreset(preset)
}

function openSchemaConfiguration(application: YingdaoApplicationOptionDto): void {
  schemaDialogApplication.value = {
    appId: application.app_id,
    appName: application.app_name,
    versionId: null,
  }
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
        <AppButton tone="primary" @click="management.openCreate">+ 新建配置</AppButton>
      </template>
    </FilterBar>

    <p v-if="management.applicationsError.value" class="parameter-preset-library-page__error">
      应用列表读取失败：{{ management.applicationsError.value }}
      <AppButton tone="text" @click="() => management.retryApplications()">重试</AppButton>
    </p>

    <ManagementListSection>
      <ParameterPresetListTable
        :rows="management.rows.value"
        :app-name-by-id="management.applicationNameById.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        @edit="openPreset"
        @copy="openPreset"
        @retry="management.retryList"
      />
    </ManagementListSection>

    <AutomationParameterPresetManagerDialog
      :show="management.editorVisible.value"
      :app-id="management.editorAppId.value"
      :schema="editorSchema"
      :application-options="management.applicationOptions.value"
      :application-options-loading="management.applicationsLoading.value"
      :initial-preset-id="management.editorPresetId.value"
      :schema-loading="configQuery.isPending.value"
      :schema-error="editorSchemaError"
      allow-schema-configuration
      @update:show="(show) => (show ? undefined : management.closeEditor())"
      @update:app-id="(appId) => (management.editorAppId.value = appId)"
      @saved="management.closeEditor"
      @configure-schema="openSchemaConfiguration"
    />

    <YingdaoApplicationConfigDialog
      v-model:show="schemaDialogOpen"
      :application="schemaDialogApplication"
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
