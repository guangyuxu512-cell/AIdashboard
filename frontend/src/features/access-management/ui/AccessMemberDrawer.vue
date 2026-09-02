<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import type {
  AccessMemberViewModel,
  AccessMembershipViewModel,
} from '@/entities/access-management'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  show: boolean
  member: AccessMemberViewModel | null
  statusChanging?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  'toggle-enabled': [member: AccessMemberViewModel]
  'reset-password': [member: AccessMemberViewModel]
  'create-membership': [member: AccessMemberViewModel]
  'edit-membership': [membership: AccessMembershipViewModel]
}>()

function scopeLabel(scope: AccessMembershipViewModel['dataScope']): string {
  return scope.toUpperCase()
}
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
          <NDescriptionsItem label="显示名">{{
            member.displayName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="登录账号">{{
            member.loginName ?? '未配置'
          }}</NDescriptionsItem>
        </NDescriptions>
        <div class="access-member-drawer__actions">
          <AppButton
            :loading="statusChanging"
            @click="$emit('toggle-enabled', member)"
          >
            {{ member.enabled ? '停用员工' : '启用员工' }}
          </AppButton>
          <AppButton tone="primary" @click="$emit('reset-password', member)"
            >重置密码</AppButton
          >
        </div>
      </section>

      <section class="access-member-drawer__section">
        <div class="access-member-drawer__section-header">
          <h3>团队关系</h3>
          <AppButton tone="text" @click="$emit('create-membership', member)"
            >加入团队</AppButton
          >
        </div>
        <article
          v-for="membership in member.memberships"
          :key="membership.membershipId"
          class="access-member-drawer__membership"
        >
          <div class="access-member-drawer__membership-heading">
            <strong>{{ membership.teamName }}</strong>
            <StatusTag
              :label="
                membership.enabled && membership.teamEnabled
                  ? '已启用'
                  : '已停用'
              "
              :tone="
                membership.enabled && membership.teamEnabled
                  ? 'success'
                  : 'neutral'
              "
            />
          </div>
          <dl>
            <div>
              <dt>角色</dt>
              <dd>
                {{
                  membership.roleCode === 'access_admin' ? '权限管理员' : '成员'
                }}
              </dd>
            </div>
            <div>
              <dt>数据范围</dt>
              <dd>{{ scopeLabel(membership.dataScope) }}</dd>
            </div>
            <div>
              <dt>功能权限</dt>
              <dd>{{ membership.moduleCodes.length }} 项</dd>
            </div>
          </dl>
          <AppButton tone="text" @click="$emit('edit-membership', membership)"
            >编辑</AppButton
          >
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

.access-member-drawer__membership dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin: var(--space-3) 0;
}

.access-member-drawer__membership dt {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.access-member-drawer__membership dd {
  margin: var(--space-1) 0 0;
}
</style>
