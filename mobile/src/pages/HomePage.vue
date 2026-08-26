<script setup lang="ts">
import { Empty as VanEmpty, Tag as VanTag } from 'vant'

import { AppPage } from '@/shared/ui'
</script>

<template>
  <AppPage class="home-page">
    <section class="home-page__surface" aria-labelledby="home-page-title">
      <VanTag type="primary" round>移动端 V1</VanTag>
      <h1 id="home-page-title" class="home-page__title">移动端功能建设中</h1>
      <p class="home-page__description">
        基础设施已就绪，业务功能将依据正式接口契约逐步开放。
      </p>
      <VanEmpty description="暂无可用业务功能" />
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
  box-shadow: var(--shadow-surface);
}

.home-page__title {
  color: var(--text-primary);
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
}

.home-page__description {
  max-width: 28em;
  color: var(--text-secondary);
}
</style>
