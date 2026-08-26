<script setup lang="ts">
import { Empty as VanEmpty } from 'vant'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { AppPage } from '@/shared/ui'

const route = useRoute()
const title = computed(() => route.meta.title)
</script>

<template>
  <AppPage class="coming-soon-page">
    <VanEmpty class="coming-soon-page__empty">
      <template #description>
        <div class="coming-soon-page__message">
          <h1>{{ title }}</h1>
          <p>功能建设中</p>
        </div>
      </template>
    </VanEmpty>
  </AppPage>
</template>

<style scoped>
.coming-soon-page {
  justify-content: center;
}

.coming-soon-page__empty {
  min-height: 100%;
}

.coming-soon-page__message {
  display: grid;
  gap: var(--space-1);
  text-align: center;
}

.coming-soon-page__message h1 {
  color: var(--text-primary);
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
}

.coming-soon-page__message p {
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
}
</style>
