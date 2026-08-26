<template>
  <div class="app-page">
    <slot />
  </div>
</template>

<style scoped>
.app-page {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 100%;
  flex-direction: column;
  gap: var(--layout-section-gap);
  padding: var(--layout-page-padding-y)
    max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--layout-page-padding-y)
    max(var(--layout-page-padding-x), var(--safe-area-left));
}
</style>
