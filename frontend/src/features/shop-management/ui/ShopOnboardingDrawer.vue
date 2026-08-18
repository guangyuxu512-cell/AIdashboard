<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import {
  NAlert,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NStep,
  NSteps,
} from 'naive-ui'
import type { SelectOption } from 'naive-ui'

import { maskCredentialIdentifier } from '@/entities/credential'
import { useDeviceListQuery } from '@/entities/device'
import {
  getPlatformDefinition,
  PLATFORM_ONBOARDING_OPTIONS,
  PlatformDisplay,
  type PlatformCode,
} from '@/entities/platform'
import { getErrorMessage } from '@/shared/api'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDrawer from '@/shared/ui/AppDrawer.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import {
  createCredentialFormSchema,
  EMPTY_CREDENTIAL_FORM,
  type CredentialFormErrors,
  type CredentialFormValue,
} from '../model/credential-form'
import CredentialFormFields from './CredentialFormFields.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  'open-legacy': []
}>()

const isDevelopment = import.meta.env.DEV
const currentStep = ref(1)
const selectedPlatform = ref<PlatformCode | null>(null)
const platformError = ref<string | null>(null)
const credential = ref<CredentialFormValue>({ ...EMPTY_CREDENTIAL_FORM })
const credentialErrors = ref<CredentialFormErrors>({})
const credentialConfigured = ref(false)
const selectedDeviceId = ref<string | null>(null)
const deviceError = ref<string | null>(null)

const deviceListParams = computed(() => ({
  page: 1,
  pageSize: 100,
  filters: {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  },
}))
const deviceQuery = useDeviceListQuery(
  deviceListParams,
  computed(() => props.show && currentStep.value >= 3),
)
const deviceOptions = computed<SelectOption[]>(() =>
  (deviceQuery.data.value?.items ?? []).map((device) => ({
    label: device.deviceName,
    value: device.deviceId,
  })),
)
const selectedDevice = computed(() =>
  (deviceQuery.data.value?.items ?? []).find(
    (device) => device.deviceId === selectedDeviceId.value,
  ),
)
const selectedPlatformMeta = computed(() =>
  selectedPlatform.value
    ? getPlatformDefinition(selectedPlatform.value)
    : undefined,
)
const loginExecutionAvailable = computed(
  () =>
    selectedPlatformMeta.value?.capabilities.shopOnboarding === 'available' &&
    selectedPlatformMeta.value.capabilities.authentication === 'available',
)
const maskedIdentifier = computed(() =>
  credential.value.loginIdentifier
    ? maskCredentialIdentifier(credential.value.loginIdentifier)
    : '—',
)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    currentStep.value = 1
    selectedPlatform.value = null
    platformError.value = null
    credential.value = { ...EMPTY_CREDENTIAL_FORM }
    credentialErrors.value = {}
    credentialConfigured.value = false
    selectedDeviceId.value = null
    deviceError.value = null
  },
)

function renderPlatformLabel(option: SelectOption) {
  const definition = getPlatformDefinition(option.value as PlatformCode)
  return h(PlatformDisplay, {
    code: option.value as PlatformCode,
    supportLabel:
      definition?.capabilities.authentication === 'available'
        ? undefined
        : '登录待接入',
  })
}

function updatePlatform(value: AppOptionValue | null): void {
  selectedPlatform.value = value as PlatformCode | null
  platformError.value = null
}

function updateDevice(value: AppOptionValue | null): void {
  selectedDeviceId.value = value as string | null
  deviceError.value = null
}

function previous(): void {
  if (currentStep.value > 1) currentStep.value -= 1
}

function next(): void {
  if (currentStep.value === 1) {
    if (!selectedPlatform.value) {
      platformError.value = '请选择平台'
      return
    }
  }
  if (currentStep.value === 2) {
    const parsed = createCredentialFormSchema(false).safeParse(credential.value)
    if (!parsed.success) {
      const errors = parsed.error.flatten().fieldErrors
      credentialErrors.value = {
        loginIdentifier: errors.loginIdentifier?.[0],
        password: errors.password?.[0],
        preferredVerificationChannel:
          errors.preferredVerificationChannel?.[0],
      }
      return
    }
    credential.value = parsed.data
    credentialErrors.value = {}
    credentialConfigured.value = true
  }
  if (currentStep.value === 3) {
    if (!selectedDeviceId.value) {
      deviceError.value = '请选择计划建立登录环境的设备'
      return
    }
  }
  if (currentStep.value < 4) currentStep.value += 1
}

function close(): void {
  credential.value = { ...EMPTY_CREDENTIAL_FORM }
  credentialErrors.value = {}
  credentialConfigured.value = false
  emit('update:show', false)
}

function updateShow(show: boolean): void {
  if (!show) {
    close()
    return
  }
  emit('update:show', true)
}

function openLegacy(): void {
  close()
  emit('open-legacy')
}
</script>

<template>
  <AppDrawer
    :show="show"
    title="新增店铺"
    size="lg"
    @update:show="updateShow"
  >
    <div class="shop-onboarding">
      <NSteps :current="currentStep" size="small">
        <NStep title="选择平台" />
        <NStep title="账号与密码" />
        <NStep title="登录设备" />
        <NStep title="准备连接" />
      </NSteps>

      <section v-if="currentStep === 1" class="shop-onboarding__step">
        <div>
          <h3>选择平台</h3>
          <p>已注册的平台都可进入接入流程，具体登录能力按平台独立演进。</p>
        </div>
        <NForm label-placement="top">
          <NFormItem
            label="平台"
            :validation-status="platformError ? 'error' : undefined"
            :feedback="platformError ?? undefined"
          >
            <AppSelect
              :model-value="selectedPlatform"
              :options="PLATFORM_ONBOARDING_OPTIONS"
              :render-label="renderPlatformLabel"
              placeholder="请选择平台"
              @update:model-value="updatePlatform"
            />
          </NFormItem>
          <NFormItem label="店铺名称">
            <span class="shop-onboarding__resolved-field">
              登录成功后自动读取
            </span>
          </NFormItem>
        </NForm>
        <NAlert
          v-if="selectedPlatform && !loginExecutionAvailable"
          type="info"
          :bordered="true"
        >
          该平台已注册，但登录执行能力尚未接入。
        </NAlert>
      </section>

      <section v-else-if="currentStep === 2" class="shop-onboarding__step">
        <div>
          <h3>配置账号与密码</h3>
          <p>
            账号密码用于 Session 失效后的授权恢复；当前 Shell 不会提前创建 Shop 或写入凭证。
          </p>
        </div>
        <NForm label-placement="top" @submit.prevent="next">
          <CredentialFormFields
            v-model="credential"
            :errors="credentialErrors"
          />
        </NForm>
      </section>

      <section v-else-if="currentStep === 3" class="shop-onboarding__step">
        <div>
          <h3>选择登录设备</h3>
          <p>这里只规划在哪台设备建立独立登录环境，不表示 Worker 在线或可用。</p>
        </div>
        <LoadingState
          v-if="deviceQuery.isPending.value"
          description="正在加载设备…"
        />
        <ErrorState
          v-else-if="deviceQuery.error.value"
          :description="getErrorMessage(deviceQuery.error.value)"
          retryable
          @retry="deviceQuery.refetch"
        />
        <NForm v-else label-placement="top">
          <NFormItem
            label="登录设备"
            :validation-status="deviceError ? 'error' : undefined"
            :feedback="deviceError ?? undefined"
          >
            <AppSelect
              :model-value="selectedDeviceId"
              :options="deviceOptions"
              :disabled="deviceOptions.length === 0"
              placeholder="请选择登录设备"
              @update:model-value="updateDevice"
            />
          </NFormItem>
          <p v-if="deviceOptions.length === 0" class="shop-onboarding__hint">
            暂无设备，请先在设备中心添加设备。
          </p>
        </NForm>
      </section>

      <section v-else class="shop-onboarding__step">
        <div>
          <h3>准备连接</h3>
          <p>以下信息将在未来 Worker 登录编排中使用。</p>
        </div>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="平台">
            <PlatformDisplay v-if="selectedPlatform" :code="selectedPlatform" />
          </NDescriptionsItem>
          <NDescriptionsItem label="登录账号">
            {{ maskedIdentifier }}
          </NDescriptionsItem>
          <NDescriptionsItem label="登录密码">
            {{ credentialConfigured ? '已配置' : '未配置' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="登录设备">
            {{ selectedDevice?.deviceName ?? '—' }}
          </NDescriptionsItem>
        </NDescriptions>
        <div class="shop-onboarding__connect-action">
          <AppButton tone="primary" disabled>打开浏览器并登录</AppButton>
          <span>待 Worker Browser Session Manager 接入</span>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="shop-onboarding__footer">
        <AppButton v-if="isDevelopment" tone="text" @click="openLegacy">
          开发：Legacy Onboarding
        </AppButton>
        <div class="shop-onboarding__footer-actions">
          <AppButton @click="close">关闭</AppButton>
          <AppButton v-if="currentStep > 1" @click="previous">上一步</AppButton>
          <AppButton
            v-if="currentStep < 4"
            tone="primary"
            @click="next"
          >
            下一步
          </AppButton>
        </div>
      </div>
    </template>
  </AppDrawer>
</template>

<style scoped>
.shop-onboarding {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.shop-onboarding__step {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}

.shop-onboarding__step h3 {
  margin-bottom: var(--space-1);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.shop-onboarding__step p,
.shop-onboarding__hint,
.shop-onboarding__connect-action span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.shop-onboarding__resolved-field {
  color: var(--text-secondary);
}

.shop-onboarding__connect-action,
.shop-onboarding__footer,
.shop-onboarding__footer-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.shop-onboarding__footer {
  width: 100%;
  justify-content: space-between;
}

.shop-onboarding__footer-actions {
  margin-left: auto;
}

@media (max-width: 720px) {
  .shop-onboarding__connect-action,
  .shop-onboarding__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .shop-onboarding__footer-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
