<script setup lang="ts">
import { computed, inject, ref } from 'vue'
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
  useShopSessionQuery,
  useValidateShopSessionMutation,
} from '@/entities/shop-session'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import { getErrorMessage } from '@/shared/api'
import AppButton from '@/shared/ui/AppButton.vue'

import CredentialFormDialog from './CredentialFormDialog.vue'
import type { CredentialFormValue } from './CredentialFormDialog.vue'
import {
  shopLoginKey,
  supportsShopLogin,
  validationFailureMessage,
} from '../model/useShopLogin'

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
const login = inject(shopLoginKey, null)
const loginFeedback = computed(() => login?.feedback.get(props.shop.shopId))
const recovering = computed(() => loginFeedback.value?.busy ?? false)
const openingOrFocusing = computed(() =>
  Boolean(loginFeedback.value?.opening || loginFeedback.value?.focusing),
)

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
  () => login?.canLogin.value && supportsShopLogin(props.shop.platform),
)

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
    message.error(validationFailureMessage(validationError))
  }
}
</script>

<template>
  <section class="shop-detail__section shop-connection-section">
    <h3>账号与连接</h3>
    <NAlert
      v-if="
        (loading || error) &&
        loginFeedback?.identityMismatch &&
        loginFeedback.error
      "
      type="error"
      :bordered="true"
      class="shop-connection-section__recovery"
    >
      {{ loginFeedback.error }}
    </NAlert>
    <LoadingState v-if="loading" description="正在加载账号与连接…" />
    <template v-else-if="error">
      <ErrorState :description="error" retryable @retry="retry" />
      <NAlert
        v-if="
          !loginFeedback?.identityMismatch &&
          loginFeedback?.success?.readRefreshFailed
        "
        type="warning"
        :bordered="true"
        class="shop-connection-section__recovery"
      >
        {{ loginFeedback.status }}
      </NAlert>
    </template>
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
            <strong>{{
              shopSession.configured ? `v${shopSession.version}` : '—'
            }}</strong>
          </div>
        </div>

        <NAlert
          v-if="loginFeedback?.status || loginFeedback?.error"
          :type="
            loginFeedback?.error
              ? 'error'
              : loginFeedback?.success?.readRefreshFailed
                ? 'warning'
                : loginFeedback?.success
                  ? 'success'
                  : 'info'
          "
          :bordered="true"
          class="shop-connection-section__recovery"
        >
          {{ loginFeedback?.error ?? loginFeedback?.status }}
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
            v-if="recoveryAvailable"
            tone="primary"
            :loading="openingOrFocusing"
            :disabled="openingOrFocusing"
            @click="login?.login(shop)"
          >
            {{
              loginFeedback?.opening
                ? '打开中…'
                : loginFeedback?.retryReady || loginFeedback?.retryBlocked
                  ? '登录'
                  : recovering
                    ? '登录中…'
                    : '登录'
            }}
          </AppButton>
          <AppButton v-if="recovering" @click="login?.cancel(shop.shopId)"
            >取消登录</AppButton
          >
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
