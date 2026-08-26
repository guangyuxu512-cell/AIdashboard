<script setup lang="ts">
import { Icon as VanIcon, NavBar as VanNavBar } from 'vant'

defineProps<{
  title: string
}>()

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <div class="mobile-detail-header" data-testid="mobile-detail-header">
    <VanNavBar :title="title" :border="false">
      <template #left>
        <button
          class="mobile-detail-header__back mobile-icon-button mobile-pressable"
          type="button"
          aria-label="返回"
          @click="emit('back')"
        >
          <VanIcon name="arrow-left" aria-hidden="true" />
        </button>
      </template>
    </VanNavBar>
  </div>
</template>

<style scoped>
.mobile-detail-header {
  padding-right: max(
    0px,
    calc(var(--safe-area-right) - var(--layout-page-padding-x))
  );
  padding-left: max(
    0px,
    calc(var(--safe-area-left) - var(--layout-page-padding-x))
  );
  background: var(--bg-surface-raised);
}

.mobile-detail-header__back {
  color: var(--color-primary);
}
</style>
