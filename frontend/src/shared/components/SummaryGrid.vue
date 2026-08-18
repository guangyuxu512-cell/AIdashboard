<script setup lang="ts">
withDefaults(defineProps<{ columns?: 2 | 3 | 4 }>(), {
  columns: 4,
})
</script>

<template>
  <div class="summary-grid" :class="`summary-grid--${columns}`">
    <slot />
  </div>
</template>

<style scoped>
.summary-grid {
  display: grid;
  gap: var(--layout-card-gap);
}

.summary-grid--2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-grid--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-grid--4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

@media (max-width: 1200px) {
  .summary-grid--3,
  .summary-grid--4 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .summary-grid--2,
  .summary-grid--3,
  .summary-grid--4 {
    grid-template-columns: 1fr;
  }
}
</style>
