<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), {
  label: '页面内容',
})

function handlePageKey(event: KeyboardEvent): void {
  if (event.target !== event.currentTarget) return
  if (event.key !== 'PageDown' && event.key !== 'PageUp') return

  event.preventDefault()
  const page = event.currentTarget as HTMLElement
  const distance = Math.max(page.clientHeight * 0.8, 1)
  page.scrollTop += event.key === 'PageDown' ? distance : -distance
}
</script>

<template>
  <div
    class="app-page mobile-scroll-container"
    role="region"
    :aria-label="label"
    tabindex="0"
    @keydown="handlePageKey"
  >
    <slot />
  </div>
</template>

<style scoped>
.app-page {
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--layout-section-gap);
  padding: var(--layout-page-padding-y)
    max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--layout-page-padding-y)
    max(var(--layout-page-padding-x), var(--safe-area-left));
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}

.app-page > :deep(*) {
  flex: none;
}
</style>
