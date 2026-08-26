<script setup lang="ts">
import { AppPage } from '@/shared/ui'
</script>

<template>
  <AppPage class="home-page">
    <section class="home-page__surface" aria-labelledby="home-page-title">
      <h1 id="home-page-title" class="home-page__title">移动端控制台</h1>
    </section>
  </AppPage>
</template>

<style scoped>
.home-page {
  justify-content: center;
}

.home-page__surface {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-4);
  text-align: center;
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.home-page__title {
  color: var(--text-primary);
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
}
</style>
