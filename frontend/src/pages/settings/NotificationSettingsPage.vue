<script setup lang="ts">
import { Bell, Plus } from '@lucide/vue'

import {
  getNotificationChannelTypeLabel,
  type NotificationChannelViewModel,
} from '@/entities/notification-channel'
import {
  NotificationChannelForm,
  useNotificationSettings,
} from '@/features/notification-settings'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const settings = useNotificationSettings()

function channelLabel(channel: NotificationChannelViewModel): string {
  return getNotificationChannelTypeLabel(channel.channelType)
}
</script>

<template>
  <div class="page-container notification-settings-page">
    <PageHeader
      title="通知配置"
      description="配置系统级 Webhook 通知通道与设备上下线事件开关。"
    >
      <template #actions>
        <AppButton tone="primary" @click="settings.startCreate">
          <Plus :size="16" />
          新增通道
        </AppButton>
      </template>
    </PageHeader>

    <PageSection fill>
      <LoadingState v-if="settings.channelsQuery.isPending.value" />
      <ErrorState
        v-else-if="settings.channelsQuery.isError.value"
        retryable
        :description="'无法加载通知配置，请检查服务连接。'"
        @retry="settings.channelsQuery.refetch()"
      />
      <div v-else class="notification-settings-layout">
        <aside class="notification-settings-list" aria-label="通知通道列表">
          <button
            v-for="channel in settings.channels.value"
            :key="channel.channelId"
            type="button"
            class="notification-channel-item"
            :class="{
              'notification-channel-item--active':
                channel.channelId === settings.selectedChannelId.value,
            }"
            @click="settings.selectChannel(channel.channelId)"
          >
            <span class="notification-channel-item__icon"><Bell :size="17" /></span>
            <span class="notification-channel-item__copy">
              <strong>{{ channel.name }}</strong>
              <small>{{ channelLabel(channel) }}</small>
            </span>
            <StatusTag
              :label="channel.enabled ? '已启用' : '已停用'"
              :tone="channel.enabled ? 'success' : 'neutral'"
            />
          </button>
          <EmptyState
            v-if="!settings.channels.value.length"
            title="尚未配置通知通道"
            description="新增飞书或企业微信群机器人 Webhook 通道。"
          />
        </aside>

        <section class="notification-settings-editor">
          <header>
            <div>
              <h2>{{ settings.creating.value ? '新增通知通道' : '编辑通知通道' }}</h2>
              <p>Webhook 明文不会从服务端返回，编辑时留空即可保留原配置。</p>
            </div>
            <StatusTag
              v-if="settings.selectedChannel.value?.webhookConfigured"
              label="Webhook 已配置"
              tone="success"
            />
          </header>
          <NotificationChannelForm
            v-if="settings.creating.value || settings.selectedChannel.value"
            :key="settings.selectedChannelId.value ?? 'new'"
            :channel="settings.selectedChannel.value"
            :creating="settings.creating.value"
            :saving="settings.saving.value"
            :testing="settings.testing.value"
            @save="settings.save"
            @test="settings.sendTest"
          />
          <EmptyState
            v-else
            title="选择或新增通知通道"
            description="通道配置用于系统级事件通知。"
          />
        </section>
      </div>
    </PageSection>
  </div>
</template>

<style scoped>
.notification-settings-page {
  min-height: 100%;
}

.notification-settings-layout {
  display: grid;
  min-height: 0;
  flex: 1;
  gap: var(--layout-card-gap);
  grid-template-columns: minmax(220px, 0.7fr) minmax(0, 2fr);
}

.notification-settings-list {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding-right: var(--space-4);
  border-right: 1px solid var(--border-subtle);
}

.notification-channel-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  color: var(--text-primary);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.notification-channel-item:hover,
.notification-channel-item--active {
  border-color: var(--border-default);
  background: var(--bg-subtle);
}

.notification-channel-item__icon {
  display: grid;
  width: var(--control-height-compact);
  height: var(--control-height-compact);
  flex: 0 0 var(--control-height-compact);
  place-items: center;
  border-radius: var(--radius-control);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.notification-channel-item__copy {
  min-width: 0;
  flex: 1;
}

.notification-channel-item__copy strong,
.notification-channel-item__copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-channel-item__copy small,
.notification-settings-editor header p {
  margin-top: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.notification-settings-editor {
  min-width: 0;
  max-width: 760px;
}

.notification-settings-editor > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.notification-settings-editor h2 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

@media (max-width: 900px) {
  .notification-settings-layout {
    grid-template-columns: 1fr;
  }

  .notification-settings-list {
    padding-right: 0;
    padding-bottom: var(--space-4);
    border-right: 0;
    border-bottom: 1px solid var(--border-subtle);
  }
}
</style>
