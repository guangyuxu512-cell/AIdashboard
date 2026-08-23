<script setup lang="ts">
import dayjs from 'dayjs'

import type { WorkerCredentialReadDto } from '@/entities/device'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  credential: WorkerCredentialReadDto | null
  loading?: boolean
  error?: string | null
  submitting?: boolean
}>()

defineEmits<{
  retry: []
  issue: []
  rotate: []
  revoke: []
}>()

function statusLabel(status: WorkerCredentialReadDto['status']): string {
  return status === 'issued'
    ? '已签发'
    : status === 'revoked'
      ? '已撤销'
      : '未签发'
}

function statusTone(status: WorkerCredentialReadDto['status']) {
  return status === 'issued'
    ? ('success' as const)
    : status === 'revoked'
      ? ('warning' as const)
      : ('neutral' as const)
}
</script>

<template>
  <section class="worker-credential">
    <div class="worker-credential__heading">
      <div>
        <h3>Worker 凭证</h3>
        <p>每台设备使用独立 Token；明文只在签发或轮换当次显示。</p>
      </div>
      <StatusTag
        v-if="credential"
        :label="statusLabel(credential.status)"
        :tone="statusTone(credential.status)"
      />
    </div>

    <LoadingState v-if="loading" description="正在读取 Worker 凭证…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <div v-else-if="credential" class="worker-credential__content">
      <dl>
        <div>
          <dt>状态</dt>
          <dd>{{ statusLabel(credential.status) }}</dd>
        </div>
        <div>
          <dt>签发时间</dt>
          <dd>
            {{
              credential.issued_at
                ? dayjs(credential.issued_at).format('YYYY-MM-DD HH:mm:ss')
                : '—'
            }}
          </dd>
        </div>
      </dl>
      <div class="worker-credential__actions">
        <AppButton
          v-if="credential.status !== 'issued'"
          tone="primary"
          :loading="submitting"
          @click="$emit('issue')"
        >
          签发 Worker Token
        </AppButton>
        <template v-else>
          <AppButton :disabled="submitting" @click="$emit('rotate')">
            轮换 Token
          </AppButton>
          <AppButton
            tone="danger"
            :disabled="submitting"
            @click="$emit('revoke')"
          >
            撤销凭证
          </AppButton>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.worker-credential {
  min-width: 0;
}

.worker-credential__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.worker-credential__heading h3,
.worker-credential__heading p {
  margin: 0;
}

.worker-credential__heading h3 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.worker-credential__heading p,
.worker-credential dt {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.worker-credential__heading p {
  margin-top: var(--space-1);
}

.worker-credential__content {
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.worker-credential dl {
  display: grid;
  margin: 0;
  gap: var(--space-3);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.worker-credential dd {
  margin: var(--space-1) 0 0;
}

.worker-credential__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
</style>
