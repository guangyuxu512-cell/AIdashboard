<script setup lang="ts">
import { useRouter } from 'vue-router'

import {
  DeviceDetailDrawer,
  DeviceCapabilityDrawer,
  DeviceFilterBar,
  DeviceFormDialog,
  DeviceListTable,
  DeviceRemoveDialog,
  YingdaoApplicationRunDialog,
  WorkerCredentialConfirmDialog,
  WorkerTokenDialog,
  useDeviceManagement,
} from '@/features/device-management'
import type { ProviderApplicationViewModel } from '@/entities/device'
import { TaskRuntimeDrawer } from '@/features/task-runtime'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useDeviceManagement()
const router = useRouter()

function openParameterPresets(application: ProviderApplicationViewModel): void {
  management.capabilityVisible.value = false
  void router.push({
    path: '/parameter-presets',
    query: { app_id: application.appId },
  })
}
</script>

<template>
  <div class="page-container device-center-page">
    <DeviceFilterBar
      v-model="management.filterDraft.value"
      :statistics="management.statistics.value"
      :refreshing="management.refreshing.value"
      @refresh="management.refreshList"
    >
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate">
          + 添加设备
        </AppButton>
      </template>
    </DeviceFilterBar>

    <ManagementListSection class="device-list-section">
      <DeviceListTable
        v-model:checked-row-keys="management.selectedDeviceIds.value"
        :rows="management.visibleRows.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        :status-changing-device-id="management.statusChangingDeviceId.value"
        @view="management.openDetail"
        @capability="management.openCapabilities"
        @toggle-enabled="management.toggleEnabled"
        @remove="management.requestRemove"
        @view-runtime="management.openTaskRuntime"
        @retry="management.retryList"
      />
      <PaginationBar
        v-model:page="management.page.value"
        :page-size="management.pageSize.value"
        :item-count="management.total.value"
        @update:page-size="management.setPageSize"
      />
    </ManagementListSection>

    <DeviceDetailDrawer
      v-model:show="management.detailVisible.value"
      :device="management.detailDevice.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      :yingdao-inventory="management.yingdaoInventory.value"
      :provider-inventory-loading="management.providerInventoryLoading.value"
      :provider-inventory-error="management.providerInventoryError.value"
      :yingdao-refreshing="management.yingdaoRefreshing.value"
      :current-execution="management.detailCurrentExecution.value"
      :bound-shop-count="management.detailBoundShopCount.value"
      :recent-executions="management.recentExecutions.value"
      :status-changing="
        management.statusChangingDeviceId.value ===
        management.detailDevice.value?.deviceId
      "
      :removing="management.removeSubmitting.value"
      :worker-credential="management.workerCredential.value"
      :worker-credential-loading="management.workerCredentialLoading.value"
      :worker-credential-error="management.workerCredentialError.value"
      :worker-credential-submitting="
        management.workerCredentialSubmitting.value
      "
      @retry="management.retryDetail"
      @retry-provider-inventory="management.retryProviderInventory"
      @refresh-yingdao="management.refreshYingdao"
      @view-capabilities="management.openCapabilities"
      @edit="management.openEdit"
      @toggle-enabled="management.toggleEnabled"
      @remove="management.requestRemove"
      @view-runtime="management.openTaskRuntime"
      @retry-worker-credential="management.retryWorkerCredential"
      @issue-worker-credential="management.issueWorkerCredential"
      @rotate-worker-credential="
        management.requestWorkerCredentialAction('rotate')
      "
      @revoke-worker-credential="
        management.requestWorkerCredentialAction('revoke')
      "
    />

    <TaskRuntimeDrawer
      v-model:show="management.runtimeVisible.value"
      :task-id="management.runtimeTaskId.value"
      :device-name="management.runtimeDeviceName.value"
    />

    <DeviceCapabilityDrawer
      v-model:show="management.capabilityVisible.value"
      :device="management.capabilityDevice.value"
      :skills="management.skillCapabilities.value"
      :skills-loading="management.skillCapabilitiesLoading.value"
      :skills-error="management.skillCapabilitiesError.value"
      :yingdao-inventory="management.capabilityYingdaoInventory.value"
      :provider-inventory-loading="
        management.capabilityProviderInventoryLoading.value
      "
      :provider-inventory-error="
        management.capabilityProviderInventoryError.value
      "
      :yingdao-refreshing="management.yingdaoRefreshing.value"
      @retry-skills="management.retrySkillCapabilities"
      @retry-provider-inventory="
        management.retryCapabilityProviderInventory
      "
      @refresh-yingdao="management.refreshYingdao"
      @parameter-presets="openParameterPresets"
      @run="management.runYingdaoApplication"
    />

    <YingdaoApplicationRunDialog
      v-model:show="management.applicationRunVisible.value"
      :application="management.selectedApplication.value"
      :device-id="management.capabilityDeviceId.value"
      @started="management.openTaskRuntime"
    />

    <DeviceFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      :submitting="management.formSubmitting.value"
      @save="management.saveDevice"
    />

    <DeviceRemoveDialog
      v-model:show="management.removeVisible.value"
      :device="management.removeDevice.value"
      :submitting="management.removeSubmitting.value"
      @confirm="management.confirmRemove"
    />

    <WorkerCredentialConfirmDialog
      v-model:show="management.credentialConfirmVisible.value"
      :action="management.credentialAction.value"
      :device-name="management.detailDevice.value?.deviceName"
      :submitting="management.workerCredentialSubmitting.value"
      @confirm="management.confirmWorkerCredentialAction"
    />

    <WorkerTokenDialog
      :show="management.workerTokenVisible.value"
      :token="management.oneTimeWorkerToken.value"
      @update:show="management.setWorkerTokenVisible"
    />
  </div>
</template>

<style scoped>
.device-center-page {
  height: 100%;
  min-height: 0;
}
</style>
