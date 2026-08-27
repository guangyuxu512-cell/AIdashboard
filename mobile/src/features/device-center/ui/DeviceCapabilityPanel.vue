<script setup lang="ts">
import {
  Button as VanButton,
  Loading as VanLoading,
  Tab as VanTab,
  Tabs as VanTabs,
} from 'vant'
import { computed, ref } from 'vue'

import type {
  DeviceProviderInventoryReadDto,
  DeviceSkillCapabilityReadDto,
  ProviderApplicationInventoryReadDto,
} from '@/entities/device'

const props = defineProps<{
  inventories: DeviceProviderInventoryReadDto[] | undefined
  capabilities: DeviceSkillCapabilityReadDto[] | undefined
  providerLoading: boolean
  providerError: boolean
  capabilityLoading: boolean
  capabilityError: boolean
}>()

const emit = defineEmits<{
  refreshCapability: []
  retryProvider: []
  retryCapability: []
  configureApplication: [application: ProviderApplicationInventoryReadDto]
  runApplication: [application: ProviderApplicationInventoryReadDto]
  configureSkill: [capability: DeviceSkillCapabilityReadDto]
  runSkill: [capability: DeviceSkillCapabilityReadDto]
}>()

const activeTab = ref<'applications' | 'skills'>('applications')
const applications = computed(
  () =>
    props.inventories?.flatMap((inventory) =>
      inventory.provider_code === 'yingdao'
        ? inventory.inventory.applications
        : [],
    ) ?? [],
)
const businessSkills = computed(
  () =>
    props.capabilities?.filter(
      (capability) => capability.classification === 'business',
    ) ?? [],
)
const applicationCount = computed(() =>
  props.inventories === undefined ? '—' : applications.value.length,
)
const skillCount = computed(() =>
  props.capabilities === undefined ? '—' : businessSkills.value.length,
)
</script>

<template>
  <section
    class="device-capability-panel mobile-section-surface"
    data-testid="device-capability-panel"
    aria-label="能力"
  >
    <div class="device-capability-panel__header">
      <VanTabs
        v-model:active="activeTab"
        shrink
        class="device-capability-panel__tabs"
        data-testid="device-capability-tabs"
      >
        <VanTab name="applications" :title="`影刀应用 ${applicationCount}`" />
        <VanTab name="skills" :title="`Skills ${skillCount}`" />
      </VanTabs>
      <VanButton
        class="device-capability-panel__refresh"
        aria-label="刷新能力"
        data-testid="device-capability-refresh"
        @click="emit('refreshCapability')"
      >
        <span>刷新</span>
      </VanButton>
    </div>

    <div
      v-if="activeTab === 'applications'"
      class="device-capability-panel__list mobile-scroll-container"
      data-testid="application-list"
      aria-label="影刀应用列表"
      tabindex="0"
    >
      <div v-if="providerLoading" class="device-capability-panel__state">
        <VanLoading size="var(--icon-size-small)">加载中</VanLoading>
      </div>
      <div v-else-if="providerError" class="device-capability-panel__state">
        <span>加载失败</span>
        <VanButton @click="emit('retryProvider')">重试</VanButton>
      </div>
      <p
        v-else-if="applications.length === 0"
        class="device-capability-panel__state"
      >
        暂无应用
      </p>
      <div
        v-for="application in applications"
        v-else
        :key="application.app_id"
        class="device-capability-panel__row"
        data-testid="application-row"
      >
        <strong class="device-capability-panel__name">
          {{ application.app_name }}
        </strong>
        <div class="device-capability-panel__actions">
          <VanButton
            class="device-capability-panel__action"
            :aria-label="`配置：${application.app_name}`"
            @click="emit('configureApplication', application)"
          >
            <span>配置</span>
          </VanButton>
          <VanButton
            class="device-capability-panel__action device-capability-panel__action--run"
            :aria-label="`运行：${application.app_name}`"
            @click="emit('runApplication', application)"
          >
            <span>运行</span>
          </VanButton>
        </div>
      </div>
    </div>

    <div
      v-else
      class="device-capability-panel__list mobile-scroll-container"
      data-testid="skill-list"
      aria-label="Skills列表"
      tabindex="0"
    >
      <div v-if="capabilityLoading" class="device-capability-panel__state">
        <VanLoading size="var(--icon-size-small)">加载中</VanLoading>
      </div>
      <div v-else-if="capabilityError" class="device-capability-panel__state">
        <span>加载失败</span>
        <VanButton @click="emit('retryCapability')">重试</VanButton>
      </div>
      <p
        v-else-if="businessSkills.length === 0"
        class="device-capability-panel__state"
      >
        暂无 Skills
      </p>
      <div
        v-for="capability in businessSkills"
        v-else
        :key="capability.skill_id"
        class="device-capability-panel__row"
        data-testid="skill-row"
      >
        <strong class="device-capability-panel__name">
          {{ capability.display_name }}
        </strong>
        <div class="device-capability-panel__actions">
          <VanButton
            v-if="capability.input_schema !== null"
            class="device-capability-panel__action"
            :aria-label="`配置：${capability.display_name}`"
            @click="emit('configureSkill', capability)"
          >
            <span>配置</span>
          </VanButton>
          <VanButton
            class="device-capability-panel__action device-capability-panel__action--run"
            :aria-label="`运行：${capability.display_name}`"
            @click="emit('runSkill', capability)"
          >
            <span>运行</span>
          </VanButton>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.device-capability-panel {
  display: grid;
  height: 200px;
  min-width: 0;
  gap: var(--space-2);
  padding: calc(var(--space-2) - var(--border-width)) var(--space-3);
  grid-template-rows: var(--touch-target-min) minmax(0, 1fr);
  overflow: hidden;
}

.device-capability-panel__header {
  display: flex;
  min-width: 0;
  gap: var(--space-1);
  align-items: center;
}

.device-capability-panel__tabs {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
}

.device-capability-panel__tabs :deep(.van-tabs__wrap) {
  height: var(--touch-target-min);
}

.device-capability-panel__tabs :deep(.van-tabs__nav) {
  background: transparent;
}

.device-capability-panel__refresh,
.device-capability-panel__action {
  height: var(--touch-target-min);
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
}

.device-capability-panel__refresh {
  flex: none;
}

.device-capability-panel__refresh span,
.device-capability-panel__action span {
  display: inline-flex;
  height: var(--control-height-compact);
  padding-inline: var(--space-2);
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-control);
}

.device-capability-panel__refresh span {
  background: var(--bg-subtle);
  border: var(--border-width) solid var(--border-subtle);
}

.device-capability-panel__list {
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: auto;
  -webkit-overflow-scrolling: touch;
}

.device-capability-panel__row {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: var(--touch-target-min);
  gap: var(--space-2);
  align-items: center;
}

.device-capability-panel__row:not(:last-child)::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: var(--border-width);
  content: '';
  background: var(--border-subtle);
}

.device-capability-panel__name {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-body);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__actions {
  display: flex;
  flex: none;
  gap: var(--space-1);
  align-items: center;
}

.device-capability-panel__action span {
  color: var(--text-secondary);
}

.device-capability-panel__action--run span {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.device-capability-panel__state {
  display: flex;
  min-height: 100%;
  gap: var(--space-2);
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}
</style>
