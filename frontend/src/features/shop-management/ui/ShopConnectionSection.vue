<script setup lang="ts">
import { computed, ref } from 'vue'
import { NDescriptions, NDescriptionsItem } from 'naive-ui'
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
} from '@/entities/shop-session'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import { getErrorMessage } from '@/shared/api'
import AppButton from '@/shared/ui/AppButton.vue'

import CredentialFormDialog from './CredentialFormDialog.vue'
import type { CredentialFormValue } from './CredentialFormDialog.vue'

const props = defineProps<{ shop: ShopListItemViewModel }>()
const message = useMessage()
const formVisible = ref(false)
const shopId = computed(() => props.shop.shopId)
const platform = computed(() => props.shop.platform)
const credentialQuery = useShopCredentialQuery(shopId, platform)
const sessionQuery = useShopSessionQuery(shopId)
const createMutation = useCreateCredentialMutation()
const updateMutation = useUpdateCredentialMutation(shopId)

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
        <NDescriptionsItem label="Cookie / Session">
          <ShopSessionStatusTag :status="shopSession.status" />
        </NDescriptionsItem>
        <NDescriptionsItem label="Session 来源">
          {{ shopSession.sourceDeviceName ?? '—' }}
        </NDescriptionsItem>
        <NDescriptionsItem label="最近采集">
          {{ shopSession.capturedAtDisplay ?? '—' }}
        </NDescriptionsItem>
        <NDescriptionsItem label="最近验证">
          {{ shopSession.validatedAtDisplay ?? '—' }}
        </NDescriptionsItem>
      </NDescriptions>

      <div class="shop-connection-section__actions">
        <AppButton tone="primary" @click="formVisible = true">
          {{ credential.configured ? '更新账号与连接' : '配置账号与连接' }}
        </AppButton>
        <AppButton disabled title="待 Worker Browser Session Manager 接入">
          打开浏览器登录
        </AppButton>
        <AppButton
          disabled
          title="待 Session Validator / Platform Connector 接入"
        >
          验证连接
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
</style>
