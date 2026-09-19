<script setup lang="ts">
import { computed } from 'vue'
import {
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NPopconfirm,
} from 'naive-ui'

import type {
  AccessMemberViewModel,
  AccessMembershipViewModel,
} from '@/entities/access-management'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  show: boolean
  member: AccessMemberViewModel | null
  statusChanging?: boolean
  teamChanging?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  'toggle-enabled': [member: AccessMemberViewModel]
  'reset-password': [member: AccessMemberViewModel]
  'move-team': [member: AccessMemberViewModel]
  'remove-team': [member: AccessMemberViewModel]
}>()

const activeMembership = computed<AccessMembershipViewModel | null>(() =>
  props.member?.memberships.find(
    (membership) => membership.enabled && membership.teamEnabled,
  ) ?? null,
)
const historicalMemberships = computed(() =>
  props.member?.memberships.filter(
    (membership) => !membership.enabled || !membership.teamEnabled,
  ) ?? [],
)
</script>

<template>
  <DetailDrawer
    :show="show"
    title="成员详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="member" class="access-member-drawer">
      <section class="access-member-drawer__section">
        <div class="access-member-drawer__section-header">
          <h3>基本账号</h3>
          <StatusTag
            :label="member.enabled ? '已启用' : '已停用'"
            :tone="member.enabled ? 'success' : 'neutral'"
          />
        </div>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="显示名">{{ member.displayName }}</NDescriptionsItem>
          <NDescriptionsItem label="登录账号">{{ member.loginName ?? '未配置' }}</NDescriptionsItem>
          <NDescriptionsItem label="账号类型">
            {{ member.isSuperAccount ? '超级账号' : '普通成员' }}
          </NDescriptionsItem>
        </NDescriptions>
        <div class="access-member-drawer__actions">
          <AppButton
            :loading="statusChanging"
            @click="$emit('toggle-enabled', member)"
          >
            {{ member.enabled ? '停用成员' : '启用成员' }}
          </AppButton>
          <AppButton tone="primary" @click="$emit('reset-password', member)">
            重置密码
          </AppButton>
        </div>
      </section>

      <section class="access-member-drawer__section">
        <div class="access-member-drawer__section-header">
          <h3>当前团队</h3>
          <AppButton
            v-if="!member.isSuperAccount"
            tone="text"
            :loading="teamChanging"
            @click="$emit('move-team', member)"
          >
            {{ activeMembership ? '调组' : '分配团队' }}
          </AppButton>
        </div>
        <template v-if="member.isSuperAccount">
          <p class="access-member-drawer__description">
            超级账号不加入业务团队，可跨团队管理资源与授权。
          </p>
        </template>
        <template v-else-if="activeMembership">
          <article class="access-member-drawer__membership">
            <div class="access-member-drawer__membership-heading">
              <strong>{{ activeMembership.teamName }}</strong>
              <StatusTag label="已生效" tone="success" />
            </div>
            <p>该成员继承此团队的模块、设备和店铺授权。</p>
            <NPopconfirm
              positive-text="确认移出"
              negative-text="取消"
              @positive-click="$emit('remove-team', member)"
            >
              <template #trigger>
                <AppButton tone="text" :loading="teamChanging">移出团队</AppButton>
              </template>
              移出后该成员将不能访问当前团队的数据和资源，历史记录会保留。
            </NPopconfirm>
          </article>
        </template>
        <NEmpty v-else size="small" description="未分配团队" />
      </section>

      <section
        v-if="!member.isSuperAccount && historicalMemberships.length"
        class="access-member-drawer__section"
      >
        <h3>历史团队关系</h3>
        <article
          v-for="membership in historicalMemberships"
          :key="membership.membershipId"
          class="access-member-drawer__membership"
        >
          <div class="access-member-drawer__membership-heading">
            <strong>{{ membership.teamName }}</strong>
            <StatusTag
              :label="membership.teamEnabled ? '已移出' : '团队已归档'"
              tone="neutral"
            />
          </div>
        </article>
      </section>
    </div>
    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.access-member-drawer {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.access-member-drawer__section-header,
.access-member-drawer__membership-heading,
.access-member-drawer__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.access-member-drawer__section h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.access-member-drawer__section-header h3 {
  margin-bottom: 0;
}

.access-member-drawer__actions {
  justify-content: flex-end;
  margin-top: var(--space-3);
}

.access-member-drawer__membership {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.access-member-drawer__membership p,
.access-member-drawer__description {
  margin: var(--space-2) 0 var(--space-3);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
</style>
