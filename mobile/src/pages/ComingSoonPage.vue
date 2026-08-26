<script setup lang="ts">
import { Empty as VanEmpty } from 'vant'
import { AppPage } from '@/shared/ui'
</script>

<template>
  <AppPage class="coming-soon-page">
    <VanEmpty class="coming-soon-page__empty" description="功能建设中" />
  </AppPage>
</template>

<style scoped>
.coming-soon-page {
  justify-content: center;
}

.coming-soon-page__empty {
  min-height: 100%;
}
</style>
