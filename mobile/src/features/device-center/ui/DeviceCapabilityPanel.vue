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
import { MobileIcon } from '@/shared/icons'

const props = withDefaults(
  defineProps<{
    inventories: DeviceProviderInventoryReadDto[] | undefined
    capabilities: DeviceSkillCapabilityReadDto[] | undefined
    providerLoading: boolean
    providerError: boolean
    capabilityLoading: boolean
    capabilityError: boolean
    refreshing?: boolean
  }>(),
  { refreshing: false },
)

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
    class="device-capability-panel"
    data-testid="device-capability-panel"
    aria-label="能力面板"
  >
    <div class="device-capability-panel__header">
      <h2 class="device-capability-panel__title">能力面板</h2>
      <button
        type="button"
        class="device-capability-panel__refresh mobile-pressable"
        :disabled="refreshing"
        :aria-busy="refreshing"
        aria-label="刷新能力"
        data-testid="device-capability-refresh"
        @click="emit('refreshCapability')"
      >
        <MobileIcon
          class="device-capability-panel__refresh-icon"
          :class="{
            'device-capability-panel__refresh-icon--active': refreshing,
          }"
          name="refresh"
        />
        <span>刷新</span>
      </button>
    </div>

    <VanTabs
      v-model:active="activeTab"
      class="device-capability-panel__tabs"
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
          <MobileIcon name="application" />
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
            <span class="device-capability-panel__action-label">配置</span>
          </VanButton>
          <VanButton
            class="device-capability-panel__action device-capability-panel__action--run"
            :aria-label="`运行：${application.app_name}`"
            @click="emit('runApplication', application)"
          >
            <span class="device-capability-panel__action-label">运行</span>
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
          <MobileIcon name="skill" />
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
            <span class="device-capability-panel__action-label">配置</span>
          </VanButton>
          <VanButton
            class="device-capability-panel__action device-capability-panel__action--run"
            :aria-label="`运行：${capability.display_name}`"
            @click="emit('runSkill', capability)"
          >
            <span class="device-capability-panel__action-label">运行</span>
          </VanButton>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.device-capability-panel {
  display: grid;
  min-width: 0;
  padding: var(--visual-v2-detail-capability-padding-top)
    var(--visual-v2-detail-capability-padding-x)
    var(--visual-v2-detail-capability-padding-bottom);
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-detail-surface-background);
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-surface-border-color);
  border-radius: var(--visual-v2-metric-strip-radius);
  box-shadow: var(--visual-v2-detail-surface-shadow);
}

.device-capability-panel__header {
  display: flex;
  min-width: 0;
  height: var(--visual-v2-detail-capability-header-height);
  margin-bottom: var(--visual-v2-detail-capability-header-gap);
  align-items: center;
  justify-content: space-between;
}

.device-capability-panel__title {
  min-width: 0;
  overflow: hidden;
  font-size: var(--typography-v2-detail-section-title-size);
  font-weight: var(--typography-v2-detail-section-title-weight);
  line-height: var(--typography-v2-detail-section-title-line-height);
  letter-spacing: var(--typography-v2-business-card-title-letter-spacing);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__refresh {
  position: relative;
  display: inline-flex;
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0 var(--visual-v2-detail-capability-action-padding-x);
  gap: var(--visual-v2-detail-capability-action-gap);
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-control);
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
}

.device-capability-panel__refresh::before {
  position: absolute;
  inset-block: calc(
    (
        var(--touch-target-min) -
          var(--visual-v2-detail-capability-action-visual-height)
      ) /
      2
  );
  inset-inline: 0;
  content: '';
  background: var(--visual-v2-detail-surface-background);
  border: var(--border-width) solid var(--visual-v2-detail-weak-border-color);
  border-radius: var(--radius-control);
}

.device-capability-panel__refresh > * {
  position: relative;
  z-index: 1;
}

.device-capability-panel__refresh-icon {
  font-size: var(--icon-size-small);
}

.device-capability-panel__refresh-icon--active {
  animation: device-capability-refresh var(--duration-normal) linear infinite;
}

.device-capability-panel__tabs {
  min-width: 0;
  margin-bottom: var(--visual-v2-detail-capability-tabs-bottom-gap);
  overflow: hidden;
}

.device-capability-panel__tabs :deep(.van-tabs__wrap) {
  position: relative;
  height: var(--visual-v2-detail-capability-tabs-height);
}

.device-capability-panel__tabs :deep(.van-tabs__wrap)::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 2;
  height: var(--border-width);
  pointer-events: none;
  content: '';
  background: var(--visual-v2-detail-divider-color);
}

.device-capability-panel__tabs :deep(.van-tabs__nav) {
  background: transparent;
}

.device-capability-panel__tabs :deep(.van-tabs__line) {
  height: calc(var(--border-width) * 2);
  background: var(--color-primary);
}

.device-capability-panel__tabs :deep(.van-tabs__content) {
  display: none;
}

.device-capability-panel__tab-label,
.device-capability-panel__tab-count {
  display: inline-block;
}

.device-capability-panel__tab-label {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-body);
}

.device-capability-panel__tab-count {
  margin-left: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-regular);
  line-height: var(--line-height-secondary);
}

.device-capability-panel__list {
  min-width: 0;
  height: var(--visual-v2-detail-capability-list-height);
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}

.device-capability-panel__row {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: var(--visual-v2-detail-capability-row-height);
  gap: var(--visual-v2-detail-capability-row-gap);
  grid-template-columns:
    var(--visual-v2-detail-capability-icon-slot) minmax(0, 1fr)
    auto;
  align-items: center;
}

.device-capability-panel__row:not(:last-child)::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: var(--border-width);
  content: '';
  background: var(--visual-v2-detail-divider-color);
}

.device-capability-panel__icon-slot {
  display: grid;
  width: var(--visual-v2-detail-capability-icon-size);
  height: var(--visual-v2-detail-capability-icon-size);
  color: var(--text-secondary);
  background: var(--visual-v2-detail-weak-background);
  border: var(--border-width) solid var(--visual-v2-detail-weak-border-color);
  border-radius: var(--radius-control);
  place-items: center;
}

.device-capability-panel__icon-slot .mobile-icon {
  width: var(--visual-v2-detail-capability-glyph-size);
  height: var(--visual-v2-detail-capability-glyph-size);
  font-size: var(--visual-v2-detail-capability-glyph-size);
}

.device-capability-panel__main-content {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.device-capability-panel__name,
.device-capability-panel__version {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-capability-panel__name {
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-label);
}

.device-capability-panel__version {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-regular);
  line-height: var(--line-height-secondary);
}

.device-capability-panel__actions {
  display: flex;
  flex: none;
  gap: var(--visual-v2-detail-capability-action-gap);
  align-items: center;
}

.device-capability-panel__action {
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
}

.device-capability-panel__action-label {
  display: inline-flex;
  height: var(--visual-v2-detail-capability-action-visual-height);
  padding-inline: var(--visual-v2-detail-capability-action-padding-x);
  align-items: center;
  justify-content: center;
  background: var(--visual-v2-detail-surface-background);
  border: var(--border-width) solid var(--visual-v2-detail-weak-border-color);
  border-radius: var(--radius-control);
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
}

.device-capability-panel__action--run .device-capability-panel__action-label {
  color: var(--color-primary);
  background: var(--visual-v2-detail-weak-background);
}

.device-capability-panel__state {
  display: flex;
  min-height: 100%;
  gap: var(--layout-capability-state-gap);
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

@keyframes device-capability-refresh {
  to {
    transform: rotate(360deg);
  }
}
</style>
