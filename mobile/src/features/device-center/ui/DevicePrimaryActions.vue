<script setup lang="ts">
import { Button as VanButton, Icon as VanIcon } from 'vant'

const emit = defineEmits<{
  runApplication: []
  refreshCapability: []
  configureParameters: []
}>()
</script>

<template>
  <section
    class="device-primary-actions mobile-section-surface"
    aria-labelledby="device-primary-actions-title"
    data-testid="device-primary-actions"
  >
    <h2 id="device-primary-actions-title">设备操作</h2>

    <VanButton
      class="device-primary-actions__button mobile-pressable"
      native-type="button"
      data-testid="device-action-run"
      @click="emit('runApplication')"
    >
      <span
        class="device-primary-actions__visual device-primary-actions__visual--primary"
      >
        <VanIcon name="play-circle-o" aria-hidden="true" />
        <span>运行应用</span>
      </span>
    </VanButton>

    <div class="device-primary-actions__secondary">
      <VanButton
        class="device-primary-actions__button mobile-pressable"
        native-type="button"
        data-testid="device-action-refresh"
        @click="emit('refreshCapability')"
      >
        <span
          class="device-primary-actions__visual device-primary-actions__visual--secondary"
        >
          <VanIcon name="replay" aria-hidden="true" />
          <span>刷新能力</span>
        </span>
      </VanButton>
      <VanButton
        class="device-primary-actions__button mobile-pressable"
        native-type="button"
        data-testid="device-action-configure"
        @click="emit('configureParameters')"
      >
        <span
          class="device-primary-actions__visual device-primary-actions__visual--secondary"
        >
          <VanIcon name="setting-o" aria-hidden="true" />
          <span>参数配置</span>
        </span>
      </VanButton>
    </div>
  </section>
</template>

<style scoped>
.device-primary-actions {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding: var(--layout-card-padding);
}

.device-primary-actions h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-primary-actions__secondary {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}

.device-primary-actions__button {
  width: 100%;
  min-width: 0;
  height: var(--touch-target-min);
  padding: 0;
  background: transparent;
  border: 0;
}

.device-primary-actions__button :deep(.van-button__content) {
  width: 100%;
  min-width: 0;
}

.device-primary-actions__button :deep(.van-button__text) {
  display: block;
  width: 100%;
  min-width: 0;
}

.device-primary-actions__visual {
  display: flex;
  width: 100%;
  min-width: 0;
  gap: var(--space-2);
  padding-inline: var(--space-3);
  align-items: center;
  justify-content: center;
  border: var(--border-width) solid transparent;
  border-radius: var(--radius-control);
}

.device-primary-actions__visual--primary {
  height: var(--control-height-default);
  color: var(--text-inverse);
  background: var(--color-primary-strong);
  border-color: var(--color-primary-strong);
}

.device-primary-actions__visual--secondary {
  height: var(--control-height-medium);
  color: var(--text-primary);
  background: var(--bg-surface-raised);
  border-color: var(--border-default);
}

.device-primary-actions__button:active
  .device-primary-actions__visual--primary {
  background: var(--color-primary-active);
  border-color: var(--color-primary-active);
}

.device-primary-actions__button:active
  .device-primary-actions__visual--secondary {
  background: var(--bg-surface-pressed);
}
</style>
