<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { NForm, NFormItem, useMessage, type SelectOption } from 'naive-ui'

import {
  DeviceConnectionStatusTag,
  DeviceIdentity,
  useDeviceListQuery,
  type DeviceListItemViewModel,
} from '@/entities/device'
import {
  useCreateShopDeviceBindingMutation,
  useUpdateShopDeviceBindingMutation,
  type ShopDeviceBindingInput,
  type ShopDeviceBindingRole,
  type ShopListItemViewModel,
} from '@/entities/shop'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{ shop: ShopListItemViewModel }>()

const message = useMessage()
const dialogVisible = ref(false)
const selectedDeviceId = ref<string | null>(null)
const selectedRole = ref<ShopDeviceBindingRole>('backup')
const deviceParams = {
  page: 1,
  pageSize: 100,
  filters: {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  },
} as const
const deviceQuery = useDeviceListQuery(deviceParams)
const createBindingMutation = useCreateShopDeviceBindingMutation()
const updateBindingMutation = useUpdateShopDeviceBindingMutation()

const devices = computed(() => deviceQuery.data.value?.items ?? [])
const activeBindings = computed(() =>
  (props.shop.deviceBindings ?? []).filter((binding) => binding.enabled),
)
const primaryBinding = computed(() =>
  activeBindings.value.find((binding) => binding.bindingRole === 'primary'),
)
const backupBindings = computed(() =>
  activeBindings.value.filter((binding) => binding.bindingRole === 'backup'),
)
const submitting = computed(
  () =>
    createBindingMutation.isPending.value ||
    updateBindingMutation.isPending.value,
)

function deviceFor(deviceId: string): DeviceListItemViewModel | undefined {
  return devices.value.find((device) => device.deviceId === deviceId)
}

function openBinding(role?: ShopDeviceBindingRole): void {
  selectedRole.value = role ?? (primaryBinding.value ? 'backup' : 'primary')
  selectedDeviceId.value = null
  dialogVisible.value = true
}

const deviceOptions = computed<SelectOption[]>(() =>
  devices.value.map((device) => {
    const binding = activeBindings.value.find(
      (item) => item.deviceId === device.deviceId,
    )
    const canPromoteBackup =
      selectedRole.value === 'primary' && binding?.bindingRole === 'backup'
    return {
      label: device.deviceName,
      value: device.deviceId,
      disabled: Boolean(binding && !canPromoteBackup),
      device,
    }
  }),
)

watch(selectedRole, () => {
  const option = deviceOptions.value.find(
    (item) => item.value === selectedDeviceId.value,
  )
  if (option?.disabled) selectedDeviceId.value = null
})

function renderDeviceLabel(option: SelectOption) {
  const device = option.device as DeviceListItemViewModel
  return h('div', { class: 'shop-device-picker__option' }, [
    h(DeviceIdentity, { name: device.deviceName }),
    h(DeviceConnectionStatusTag, { status: device.runtimeStatus }),
  ])
}

function updateDevice(value: AppOptionValue | null): void {
  selectedDeviceId.value = value as string | null
}

async function saveBinding(input: ShopDeviceBindingInput): Promise<void> {
  const existing = (props.shop.deviceBindings ?? []).find(
    (binding) => binding.deviceId === input.deviceId,
  )
  if (existing) {
    await updateBindingMutation.mutateAsync({
      shopId: props.shop.shopId,
      input,
    })
  } else {
    await createBindingMutation.mutateAsync({
      shopId: props.shop.shopId,
      input,
    })
  }
}

async function submitBinding(): Promise<void> {
  if (!selectedDeviceId.value) {
    message.warning('请选择设备')
    return
  }
  const nextBinding: ShopDeviceBindingInput = {
    deviceId: selectedDeviceId.value,
    bindingRole: selectedRole.value,
    enabled: true,
  }
  const oldPrimary = primaryBinding.value
  let oldPrimaryDisabled = false
  try {
    if (
      nextBinding.bindingRole === 'primary' &&
      oldPrimary &&
      oldPrimary.deviceId !== nextBinding.deviceId
    ) {
      await updateBindingMutation.mutateAsync({
        shopId: props.shop.shopId,
        input: {
          deviceId: oldPrimary.deviceId,
          bindingRole: 'primary',
          enabled: false,
        },
      })
      oldPrimaryDisabled = true
    }
    await saveBinding(nextBinding)
    dialogVisible.value = false
    message.success(
      nextBinding.bindingRole === 'primary' ? '主设备已更新' : '备用设备已绑定',
    )
  } catch (error) {
    if (oldPrimaryDisabled && oldPrimary) {
      try {
        await updateBindingMutation.mutateAsync({
          shopId: props.shop.shopId,
          input: {
            deviceId: oldPrimary.deviceId,
            bindingRole: 'primary',
            enabled: true,
          },
        })
      } catch {
        message.error('主设备恢复失败，请刷新后检查绑定状态')
      }
    }
    message.error(getErrorMessage(error))
  }
}

async function unbind(
  deviceId: string,
  role: ShopDeviceBindingRole,
): Promise<void> {
  try {
    await updateBindingMutation.mutateAsync({
      shopId: props.shop.shopId,
      input: { deviceId, bindingRole: role, enabled: false },
    })
    message.success('设备已解绑')
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <section class="shop-device-bindings">
    <div class="shop-device-bindings__heading">
      <h3>执行设备</h3>
      <AppButton tone="text" @click="openBinding()">+ 绑定设备</AppButton>
    </div>

    <div v-if="primaryBinding" class="shop-device-bindings__group">
      <span class="shop-device-bindings__label">主设备</span>
      <div class="shop-device-bindings__row">
        <DeviceIdentity :name="primaryBinding.deviceName" />
        <DeviceConnectionStatusTag
          :status="
            deviceFor(primaryBinding.deviceId)?.runtimeStatus ?? 'unavailable'
          "
        />
        <div class="shop-device-bindings__actions">
          <AppButton tone="text" @click="openBinding('primary')"
            >更换</AppButton
          >
          <AppButton
            tone="text"
            @click="unbind(primaryBinding.deviceId, 'primary')"
          >
            解绑
          </AppButton>
        </div>
      </div>
    </div>

    <div v-if="backupBindings.length" class="shop-device-bindings__group">
      <span class="shop-device-bindings__label">备用设备</span>
      <div
        v-for="binding in backupBindings"
        :key="binding.deviceId"
        class="shop-device-bindings__row"
      >
        <DeviceIdentity :name="binding.deviceName" />
        <DeviceConnectionStatusTag
          :status="deviceFor(binding.deviceId)?.runtimeStatus ?? 'unavailable'"
        />
        <div class="shop-device-bindings__actions">
          <AppButton tone="text" @click="unbind(binding.deviceId, 'backup')">
            解绑
          </AppButton>
        </div>
      </div>
    </div>

    <div v-if="!activeBindings.length" class="shop-device-bindings__empty">
      <span>暂无绑定设备</span>
      <AppButton tone="primary" @click="openBinding('primary')"
        >绑定设备</AppButton
      >
    </div>

    <FormDialog
      v-model:show="dialogVisible"
      title="绑定执行设备"
      size="sm"
      :submitting="submitting"
      @submit="submitBinding"
      @cancel="dialogVisible = false"
    >
      <NForm label-placement="top">
        <NFormItem label="设备">
          <AppSelect
            :model-value="selectedDeviceId"
            :options="deviceOptions"
            :loading="deviceQuery.isPending.value"
            :render-label="renderDeviceLabel"
            filterable
            placeholder="选择真实设备（允许离线设备）"
            @update:model-value="updateDevice"
          />
        </NFormItem>
        <NFormItem label="角色">
          <AppRadio
            v-model="selectedRole"
            :options="[
              { label: '主设备', value: 'primary' },
              { label: '备用设备', value: 'backup' },
            ]"
          />
        </NFormItem>
        <div class="shop-device-picker__hint">
          <StatusTag label="在线" tone="success" /> 与
          <StatusTag label="离线" tone="neutral" /> 均可绑定；运行状态来自真实
          Worker 心跳。
        </div>
      </NForm>
    </FormDialog>
  </section>
</template>

<style scoped>
.shop-device-bindings {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.shop-device-bindings__heading,
.shop-device-bindings__row {
  display: flex;
  min-width: 0;
  align-items: center;
}

.shop-device-bindings__heading {
  justify-content: space-between;
}

.shop-device-bindings__heading h3 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.shop-device-bindings__group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.shop-device-bindings__label {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.shop-device-bindings__row {
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

.shop-device-bindings__row :deep(.device-identity) {
  flex: 1;
}

.shop-device-bindings__actions {
  display: inline-flex;
  margin-left: auto;
  gap: var(--space-1);
}

.shop-device-bindings__empty {
  display: flex;
  min-height: 104px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: var(--space-3);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-card);
  color: var(--text-tertiary);
}

:deep(.shop-device-picker__option) {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.shop-device-picker__hint {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
