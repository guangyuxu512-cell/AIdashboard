<script setup lang="ts">
import {
  Button as VanButton,
  Icon as VanIcon,
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
const capabilityIconNames = {
  application: 'apps-o',
  skill: 'setting-o',
} as const

function formatSkillVersion(version: string): string | null {
  const normalized = version.trim()
  if (!normalized) return null
  return normalized.toLowerCase().startsWith('v')
    ? normalized
    : `v${normalized}`
}
</script>

<template>
  <section
    class="device-capability-panel mobile-section-surface"
    data-testid="device-capability-panel"
    aria-label="能力"
  >
    <div class="device-capability-panel__header">
      <h2 class="device-capability-panel__title">能力</h2>
      <button
        type="button"
        class="device-capability-panel__refresh mobile-icon-button mobile-pressable"
        aria-label="刷新能力"
        data-testid="device-capability-refresh"
        @click="emit('refreshCapability')"
      >
        <VanIcon name="replay" aria-hidden="true" />
      </button>
    </div>

    <VanTabs
      v-model:active="activeTab"
      class="device-capability-panel__tabs mobile-segmented-tabs"
      data-testid="device-capability-tabs"
    >
      <VanTab name="applications">
        <template #title>
          <span class="device-capability-panel__tab-label">影刀应用</span>
          <span class="device-capability-panel__tab-count">
            {{ applicationCount }}
          </span>
        </template>
      </VanTab>
      <VanTab name="skills">
        <template #title>
          <span class="device-capability-panel__tab-label">Skills</span>
          <span class="device-capability-panel__tab-count">
            {{ skillCount }}
          </span>
        </template>
      </VanTab>
    </VanTabs>

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
        <span
          class="device-capability-panel__icon-slot"
          data-testid="capability-icon-slot"
          data-capability-type="application"
          aria-hidden="true"
        >
          <VanIcon :name="capabilityIconNames.application" />
        </span>
        <span class="device-capability-panel__main-content">
          <strong class="device-capability-panel__name">
            {{ application.app_name }}
          </strong>
        </span>
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
        <span
          class="device-capability-panel__icon-slot"
          data-testid="capability-icon-slot"
          data-capability-type="skill"
          aria-hidden="true"
        >
          <VanIcon :name="capabilityIconNames.skill" />
        </span>
        <span class="device-capability-panel__main-content">
          <strong class="device-capability-panel__name">
            {{ capability.display_name }}
          </strong>
          <span
            v-if="formatSkillVersion(capability.version)"
            class="device-capability-panel__version"
            data-testid="capability-version"
          >
            {{ formatSkillVersion(capability.version) }}
          </span>
        </span>
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
  height: var(--layout-capability-panel-height);
  max-height: var(--layout-capability-panel-height);
  min-width: 0;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  grid-template-rows: var(--touch-target-min) var(--touch-target-min) minmax(
      0,
      1fr
    );
  overflow: hidden;
}

.device-capability-panel__header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
}

.device-capability-panel__title {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__tabs {
  min-width: 0;
  overflow: hidden;
}

.device-capability-panel__tab-label,
.device-capability-panel__tab-count {
  display: inline-block;
}

.device-capability-panel__tab-label {
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
}

.device-capability-panel__tab-count {
  margin-left: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-regular);
  line-height: var(--line-height-caption);
}

.device-capability-panel__tabs
  :deep(.van-tab--active)
  .device-capability-panel__tab-count {
  color: var(--text-secondary);
}

.device-capability-panel__refresh {
  flex: none;
  color: var(--text-secondary);
}

.device-capability-panel__refresh::before {
  inset: calc((var(--touch-target-min) - var(--control-height-compact)) / 2);
  background: var(--bg-subtle);
  border: var(--border-width) solid var(--border-subtle);
  box-shadow: var(--shadow-card-pressed);
}

.device-capability-panel__refresh :deep(.van-icon) {
  font-size: var(--icon-size-small);
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
  min-height: var(--layout-capability-row-min-height);
  gap: var(--space-2);
  align-items: center;
}

.device-capability-panel__icon-slot {
  display: grid;
  width: var(--layout-capability-icon-slot-width);
  flex: 0 0 var(--layout-capability-icon-slot-width);
  color: var(--text-secondary);
  font-size: var(--icon-size-capability-row);
  place-items: center;
}

.device-capability-panel__main-content {
  display: grid;
  min-width: 0;
  flex: 1 1 auto;
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
  overflow: hidden;
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-body);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__version {
  min-width: 0;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__actions {
  display: flex;
  flex: none;
  gap: var(--space-1);
  align-items: center;
}

.device-capability-panel__action {
  height: var(--touch-target-min);
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
}

.device-capability-panel__action span {
  display: inline-flex;
  height: var(--control-height-capability-action);
  padding-inline: var(--space-2);
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-control);
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
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
