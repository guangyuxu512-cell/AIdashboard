<script setup lang="ts">
import { computed, h, onBeforeUnmount, ref, watch } from 'vue'
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

import {
  getPlatformDefinition,
  PLATFORM_ONBOARDING_OPTIONS,
  PlatformDisplay,
  type PlatformCode,
} from '@/entities/platform'
import { getErrorMessage } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'
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
import { startManagementLoginPolling } from '../model/management-login-poller'
import CredentialFormFields from './CredentialFormFields.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  completed: [shopId: string]
}>()

const currentStep = ref(1)
const selectedPlatform = ref<PlatformCode | null>(null)
const platformError = ref<string | null>(null)
const credential = ref<CredentialFormValue>({ ...EMPTY_CREDENTIAL_FORM })
const credentialErrors = ref<CredentialFormErrors>({})
const loginStatus = ref<ManagementLoginStatusResult | null>(null)
const completedResult = ref<ManagementLoginCompleteResult | null>(null)
const actionError = ref<string | null>(null)
const openingLogin = ref(false)
const completing = ref(false)
const authStore = useAuthStore()
let stopLoginPolling: (() => void) | undefined

const selectedPlatformMeta = computed(() =>
  selectedPlatform.value
    ? getPlatformDefinition(selectedPlatform.value)
    : undefined,
)
const loginAvailable = computed(
  () =>
    (selectedPlatform.value === 'douyin' || selectedPlatform.value === 'pdd') &&
    selectedPlatformMeta.value?.capabilities.shopOnboarding === 'available' &&
    selectedPlatformMeta.value.capabilities.authentication === 'available' &&
    selectedPlatformMeta.value.capabilities.sessionCapture === 'available',
)
const loginStateType = computed(() => {
  if (actionError.value || loginStatus.value?.status === 'failed')
    return 'error'
  if (loginStatus.value?.status === 'identified') return 'success'
  if (loginStatus.value?.status === 'closed') return 'warning'
  return 'info'
})

watch(
  () => props.show,
  (show) => {
    if (show) reset()
  },
)

onBeforeUnmount(() => {
  stopPolling()
  void closeLoginAttempt()
})

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

function previous(): void {
  if (currentStep.value > 1 && currentStep.value < 4) currentStep.value -= 1
}

function next(): void {
  if (currentStep.value === 1) {
    if (!selectedPlatform.value) {
      platformError.value = '请选择平台'
      return
    }
    if (!loginAvailable.value) {
      platformError.value = '该平台的真实登录识别尚未接入'
      return
    }
  }
  if (currentStep.value === 2 && !validateCredential()) return
  if (currentStep.value < 3) currentStep.value += 1
}

function validateCredential(): boolean {
  const parsed = createCredentialFormSchema(false).safeParse(credential.value)
  if (parsed.success) {
    credential.value = parsed.data
    credentialErrors.value = {}
    return true
  }
  const errors = parsed.error.flatten().fieldErrors
  credentialErrors.value = {
    loginIdentifier: errors.loginIdentifier?.[0],
    password: errors.password?.[0],
    preferredVerificationChannel: errors.preferredVerificationChannel?.[0],
  }
  return false
}

async function openLogin(): Promise<void> {
  if (!loginAvailable.value || !selectedPlatform.value) return
  if (selectedPlatform.value !== 'douyin' && selectedPlatform.value !== 'pdd') {
    return
  }
  if (!window.desktop?.managementLogin) {
    actionError.value = '请在 Electron 中控台中完成管理端登录'
    return
  }
  if (!authStore.activeTeamId) {
    actionError.value = '请先选择当前团队'
    return
  }
  openingLogin.value = true
  actionError.value = null
  try {
    loginStatus.value = await window.desktop.managementLogin.open({
      platform: selectedPlatform.value,
      teamId: authStore.activeTeamId,
      attemptId: loginStatus.value?.attemptId,
    })
    startPolling()
  } catch (error) {
    actionError.value = getErrorMessage(error)
  } finally {
    openingLogin.value = false
  }
}

function startPolling(): void {
  stopPolling()
  if (!loginStatus.value?.attemptId || !window.desktop?.managementLogin) return
  stopLoginPolling = startManagementLoginPolling({
    attemptId: loginStatus.value.attemptId,
    getStatus: window.desktop.managementLogin.getStatus,
    onStatus(status) {
      loginStatus.value = status
      if (status.status === 'identified') currentStep.value = 4
    },
    onError(error) {
      actionError.value = getErrorMessage(error)
    },
  })
}

function stopPolling(): void {
  stopLoginPolling?.()
  stopLoginPolling = undefined
}

async function completeOnboarding(): Promise<void> {
  if (
    !loginStatus.value?.attemptId ||
    !loginStatus.value.sessionCaptured ||
    !window.desktop?.managementLogin
  ) {
    actionError.value = '尚未识别有效店铺登录会话'
    return
  }
  if (!validateCredential()) {
    currentStep.value = 2
    return
  }
  completing.value = true
  actionError.value = null
  try {
    completedResult.value = await window.desktop.managementLogin.complete({
      attemptId: loginStatus.value.attemptId,
      loginIdentifier: credential.value.loginIdentifier,
      secret: credential.value.password,
      preferredVerificationChannel:
        credential.value.preferredVerificationChannel,
    })
    credential.value.password = ''
    currentStep.value = 5
    emit('completed', completedResult.value.shopId)
  } catch (error) {
    actionError.value = getErrorMessage(error)
  } finally {
    completing.value = false
  }
}

async function closeLoginAttempt(): Promise<void> {
  const attemptId = loginStatus.value?.attemptId
  if (attemptId && window.desktop?.managementLogin) {
    await window.desktop.managementLogin.close(attemptId).catch(() => undefined)
  }
}

function reset(): void {
  stopPolling()
  currentStep.value = 1
  selectedPlatform.value = null
  platformError.value = null
  credential.value = { ...EMPTY_CREDENTIAL_FORM }
  credentialErrors.value = {}
  loginStatus.value = null
  completedResult.value = null
  actionError.value = null
  openingLogin.value = false
  completing.value = false
}

function close(): void {
  stopPolling()
  void closeLoginAttempt()
  credential.value = { ...EMPTY_CREDENTIAL_FORM }
  emit('update:show', false)
}

function updateShow(show: boolean): void {
  if (!show) close()
  else emit('update:show', true)
}
</script>

<template>
  <AppDrawer :show="show" title="新增店铺" size="lg" @update:show="updateShow">
    <div class="shop-onboarding">
      <NSteps :current="currentStep" size="small">
        <NStep title="选择平台" />
        <NStep title="账号与密码" />
        <NStep title="登录并识别" />
        <NStep title="确认店铺" />
        <NStep title="完成" />
      </NSteps>

      <section v-if="currentStep === 1" class="shop-onboarding__step">
        <div>
          <h3>选择平台</h3>
          <p>当前只开放已有真实登录识别依据的平台。</p>
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
              登录成功后由平台自动识别
            </span>
          </NFormItem>
        </NForm>
      </section>

      <section v-else-if="currentStep === 2" class="shop-onboarding__step">
        <div>
          <h3>账号与密码</h3>
          <p>
            本轮登录窗口不自动填充；凭证只在接入完成时发送到服务器加密保存。
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
          <h3>登录并识别</h3>
          <p>
            独立登录窗口保存在当前管理电脑；验证码、扫码、滑块和 App
            确认由你人工完成。
          </p>
        </div>
        <div class="shop-onboarding__connect-action">
          <AppButton tone="primary" :loading="openingLogin" @click="openLogin">
            {{
              loginStatus?.status === 'closed'
                ? '重新打开登录'
                : '打开浏览器登录'
            }}
          </AppButton>
        </div>
        <NAlert
          v-if="loginStatus || actionError"
          :type="loginStateType"
          :bordered="true"
        >
          {{ actionError ?? loginStatus?.message }}
        </NAlert>
      </section>

      <section v-else-if="currentStep === 4" class="shop-onboarding__step">
        <div>
          <h3>确认店铺</h3>
          <p>以下身份来自平台账号接口，确认后才会原子创建正式店铺。</p>
        </div>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="平台">
            <PlatformDisplay
              v-if="loginStatus?.identity"
              :code="loginStatus.identity.platform"
            />
            <span v-else>{{ selectedPlatformMeta?.label ?? '—' }}</span>
          </NDescriptionsItem>
          <NDescriptionsItem label="平台店铺名称">
            {{
              loginStatus?.identity?.shopDisplayName ??
              '将在完成接入时由服务器验证'
            }}
          </NDescriptionsItem>
          <NDescriptionsItem label="平台店铺 ID">
            {{
              loginStatus?.identity?.platformShopId ??
              '将在完成接入时由服务器验证'
            }}
          </NDescriptionsItem>
          <NDescriptionsItem label="登录状态">已识别</NDescriptionsItem>
          <NDescriptionsItem label="登录会话">
            {{ loginStatus?.sessionCaptured ? '已采集' : '未采集' }}
          </NDescriptionsItem>
        </NDescriptions>
        <NAlert v-if="actionError" type="error" :bordered="true">
          {{ actionError }}
        </NAlert>
      </section>

      <section v-else class="shop-onboarding__step">
        <div>
          <h3>接入成功</h3>
          <p>店铺、加密凭证与加密 Session 已由服务器一致保存。</p>
        </div>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="平台店铺名称">
            {{ completedResult?.shopDisplayName ?? '—' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="平台店铺 ID">
            {{ completedResult?.platformShopId ?? '—' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="登录账号">
            {{ completedResult?.maskedIdentifier ?? '—' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="登录会话">
            已采集 · v{{ completedResult?.sessionVersion ?? 1 }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>
    </div>

    <template #footer>
      <div class="shop-onboarding__footer">
        <AppButton @click="close">
          {{ currentStep === 5 ? '关闭' : '取消' }}
        </AppButton>
        <div class="shop-onboarding__footer-actions">
          <AppButton
            v-if="currentStep > 1 && currentStep < 4"
            @click="previous"
          >
            上一步
          </AppButton>
          <AppButton v-if="currentStep < 3" tone="primary" @click="next">
            下一步
          </AppButton>
          <AppButton
            v-if="currentStep === 4"
            tone="primary"
            :loading="completing"
            @click="completeOnboarding"
          >
            完成接入
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

.shop-onboarding__step p {
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
