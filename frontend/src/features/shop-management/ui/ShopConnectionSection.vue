<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { NAlert, NDescriptions, NDescriptionsItem } from 'naive-ui'
import { useMessage } from 'naive-ui'

import {
  useCreateCredentialMutation,
  useShopCredentialQuery,
  useUpdateCredentialMutation,
} from '@/entities/credential'
import type { ShopListItemViewModel } from '@/entities/shop'
import {
  ShopSessionStatusTag,
  useAcquireShopSessionRefreshLeaseMutation,
  useReleaseShopSessionRefreshLeaseMutation,
  useShopSessionQuery,
  useValidateShopSessionMutation,
  shopSessionDataSource,
} from '@/entities/shop-session'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import { getErrorMessage } from '@/shared/api'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/shared/ui/AppButton.vue'

import CredentialFormDialog from './CredentialFormDialog.vue'
import type { CredentialFormValue } from './CredentialFormDialog.vue'
import { startManagementLoginPolling } from '../model/management-login-poller'

const props = defineProps<{ shop: ShopListItemViewModel }>()
const emit = defineEmits<{ sessionUpdated: [] }>()
const message = useMessage()
const formVisible = ref(false)
const shopId = computed(() => props.shop.shopId)
const platform = computed(() => props.shop.platform)
const credentialQuery = useShopCredentialQuery(shopId, platform)
const sessionQuery = useShopSessionQuery(shopId)
const createMutation = useCreateCredentialMutation()
const updateMutation = useUpdateCredentialMutation(shopId)
const validateSessionMutation = useValidateShopSessionMutation(shopId)
const acquireLeaseMutation = useAcquireShopSessionRefreshLeaseMutation(shopId)
const releaseLeaseMutation = useReleaseShopSessionRefreshLeaseMutation()
const recoveryStatus = ref<ManagementLoginStatusResult | null>(null)
const recoveryError = ref<string | null>(null)
const recovering = ref(false)
const activeLease = ref<{ shopId: string; leaseId: string } | null>(null)
const authStore = useAuthStore()
let stopRecoveryPolling: (() => void) | undefined

const credential = computed(() => credentialQuery.data.value ?? null)
const shopSession = computed(() => sessionQuery.data.value ?? null)
const loading = computed(
  () => credentialQuery.isPending.value || sessionQuery.isPending.value,
)
const error = computed(() => {
  const queryError = credentialQuery.error.value ?? sessionQuery.error.value
  return queryError ? getErrorMessage(queryError) : null
})
const submitting = computed(
  () => createMutation.isPending.value || updateMutation.isPending.value,
)
const verificationChannelLabel = computed(() => {
  const labels = {
    manual: '人工',
    email: '邮箱',
    sms_hardware: '短信硬件',
  }
  const channel = credential.value?.preferredVerificationChannel
  return channel ? labels[channel] : '未配置'
})
const recoveryAvailable = computed(
  () =>
    shopSession.value?.configured &&
    (props.shop.platform === 'douyin' || props.shop.platform === 'pdd') &&
    (shopSession.value.status === 'invalid' ||
      shopSession.value.status === 'refresh_required'),
)

onBeforeUnmount(() => {
  stopRecoveryPolling?.()
  void cancelRecovery()
})

function retry(): void {
  void Promise.all([credentialQuery.refetch(), sessionQuery.refetch()])
}

async function saveCredential(value: CredentialFormValue): Promise<void> {
  try {
    if (credential.value?.configured && credential.value.credentialId) {
      await updateMutation.mutateAsync({
        credentialId: credential.value.credentialId,
        ...(value.loginIdentifier.trim()
          ? { loginIdentifier: value.loginIdentifier.trim() }
          : {}),
        ...(value.password ? { password: value.password } : {}),
        preferredVerificationChannel: value.preferredVerificationChannel,
      })
      message.success('账号与连接已更新')
    } else {
      await createMutation.mutateAsync({
        shopId: props.shop.shopId,
        platform: props.shop.platform,
        loginIdentifier: value.loginIdentifier.trim(),
        password: value.password,
        preferredVerificationChannel: value.preferredVerificationChannel,
      })
      message.success('账号与连接已配置')
    }
    formVisible.value = false
  } catch (saveError) {
    message.error(getErrorMessage(saveError))
  } finally {
    createMutation.reset()
    updateMutation.reset()
  }
}

async function validateSession(): Promise<void> {
  try {
    await validateSessionMutation.mutateAsync()
    emit('sessionUpdated')
    message.success('登录会话验证有效')
  } catch (validationError) {
    await sessionQuery.refetch()
    emit('sessionUpdated')
    message.error(getErrorMessage(validationError))
  }
}

async function recoverSession(): Promise<void> {
  if (props.shop.platform !== 'douyin' && props.shop.platform !== 'pdd') {
    return
  }
  if (!window.desktop?.managementLogin) {
    recoveryError.value = '请在 Electron 中控台中恢复登录会话'
    return
  }
  if (!authStore.activeTeamId) {
    recoveryError.value = '请先选择当前团队'
    return
  }
  recovering.value = true
  recoveryError.value = null
  try {
    const lease = await acquireLeaseMutation.mutateAsync()
    activeLease.value = { shopId: lease.shopId, leaseId: lease.leaseId }
    recoveryStatus.value = await window.desktop.managementLogin.open({
      platform: props.shop.platform,
      teamId: authStore.activeTeamId,
      recovery: {
        shopId: lease.shopId,
        leaseId: lease.leaseId,
        expectedVersion: lease.expectedVersion,
      },
    })
    stopRecoveryPolling?.()
    stopRecoveryPolling = startManagementLoginPolling({
      attemptId: recoveryStatus.value.attemptId,
      getStatus: window.desktop.managementLogin.getStatus,
      async onStatus(status) {
        recoveryStatus.value = status
        if (status.status !== 'identified') {
          if (status.status === 'closed' || status.status === 'failed') {
            recovering.value = false
            activeLease.value = null
            void window.desktop?.managementLogin?.close(status.attemptId)
          }
          return
        }
        const result = await window.desktop!.managementLogin!.refresh(
          status.attemptId,
        )
        recovering.value = false
        recoveryStatus.value = null
        activeLease.value = null
        await shopSessionDataSource.confirmRecovery(
          result.shopId,
          result.sessionVersion,
          result.validatedAt,
        )
        await sessionQuery.refetch()
        emit('sessionUpdated')
        if (result.profileMappingWarning) {
          message.warning(result.profileMappingWarning)
        } else {
          message.success(`登录会话已恢复并验证有效 · v${result.sessionVersion}`)
        }
      },
      onError(error) {
        recovering.value = false
        recoveryError.value = getErrorMessage(error)
        const attemptId = recoveryStatus.value?.attemptId
        if (attemptId) {
          void window.desktop?.managementLogin?.close(attemptId)
        }
        activeLease.value = null
      },
    })
  } catch (error) {
    recovering.value = false
    recoveryError.value = getErrorMessage(error)
    if (activeLease.value && !recoveryStatus.value?.attemptId) {
      await releaseLeaseMutation
        .mutateAsync(activeLease.value)
        .catch(() => undefined)
      activeLease.value = null
    }
  }
}

async function cancelRecovery(): Promise<void> {
  stopRecoveryPolling?.()
  stopRecoveryPolling = undefined
  const attemptId = recoveryStatus.value?.attemptId
  if (attemptId && window.desktop?.managementLogin) {
    await window.desktop.managementLogin.close(attemptId).catch(() => undefined)
  } else if (activeLease.value) {
    await releaseLeaseMutation
      .mutateAsync(activeLease.value)
      .catch(() => undefined)
  }
  recoveryStatus.value = null
  recovering.value = false
  recoveryError.value = null
  activeLease.value = null
  releaseLeaseMutation.reset()
}
</script>

<template>
  <section class="shop-detail__section shop-connection-section">
    <h3>账号与连接</h3>
    <LoadingState v-if="loading" description="正在加载账号与连接…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="retry"
    />
    <template v-else-if="credential && shopSession">
      <NDescriptions :column="1" label-placement="left" bordered>
        <NDescriptionsItem label="登录账号">
          {{ credential.maskedIdentifier ?? '未配置' }}
        </NDescriptionsItem>
        <NDescriptionsItem label="登录密码">
          {{ credential.passwordConfigured ? '已配置' : '未配置' }}
        </NDescriptionsItem>
        <NDescriptionsItem label="首选验证">
          {{ verificationChannelLabel }}
        </NDescriptionsItem>
      </NDescriptions>

      <div class="shop-session-card">
        <div class="shop-session-card__header">
          <h4>登录会话</h4>
          <ShopSessionStatusTag :status="shopSession.status" />
        </div>

        <div class="shop-session-card__metadata">
          <div>
            <span>最近验证</span>
            <strong>{{ shopSession.validatedAtDisplay ?? '—' }}</strong>
          </div>
          <div>
            <span>最近采集</span>
            <strong>{{ shopSession.capturedAtDisplay ?? '—' }}</strong>
          </div>
          <div>
            <span>Session 版本</span>
            <strong>{{ shopSession.configured ? `v${shopSession.version}` : '—' }}</strong>
          </div>
        </div>

        <NAlert
          v-if="recoveryStatus || recoveryError"
          :type="recoveryError ? 'error' : 'info'"
          :bordered="true"
          class="shop-connection-section__recovery"
        >
          {{
            recoveryError ??
            `${recoveryStatus?.profileReused ? '已复用本机登录环境' : '已创建本机登录环境'}；${recoveryStatus?.message}`
          }}
        </NAlert>

        <div class="shop-connection-section__actions">
          <AppButton
            :tone="shopSession.status === 'captured' ? 'primary' : 'secondary'"
            :loading="validateSessionMutation.isPending.value"
            :disabled="!shopSession.configured || recovering"
            @click="validateSession"
          >
            验证会话
          </AppButton>
          <AppButton
            v-if="recoveryAvailable && !recovering"
            tone="primary"
            :loading="acquireLeaseMutation.isPending.value"
            @click="recoverSession"
          >
            重新登录
          </AppButton>
          <AppButton v-if="recovering" @click="cancelRecovery">取消恢复</AppButton>
        </div>
      </div>

      <div class="shop-connection-section__credential-action">
        <AppButton @click="formVisible = true">
          {{ credential.configured ? '更新账号与连接' : '配置账号与连接' }}
        </AppButton>
      </div>

      <CredentialFormDialog
        v-model:show="formVisible"
        :credential="credential"
        :submitting="submitting"
        @save="saveCredential"
      />
    </template>
  </section>
</template>

<style scoped>
.shop-connection-section h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.shop-connection-section__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.shop-connection-section__credential-action {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-3);
}

.shop-session-card {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

.shop-session-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.shop-session-card__header h4 {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}

.shop-session-card__metadata {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-3);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.shop-session-card__metadata div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.shop-session-card__metadata span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.shop-session-card__metadata strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-connection-section__recovery {
  margin-top: var(--space-3);
}

@media (max-width: 640px) {
  .shop-session-card__metadata {
    grid-template-columns: 1fr;
  }
}
</style>
