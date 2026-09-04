<script setup lang="ts">
import { Empty as VanEmpty } from 'vant'

import { AppPage } from '@/shared/ui'
</script>

<template>
  <AppPage class="permission-denied-page" label="无权访问">
    <VanEmpty description="无权访问" />
  </AppPage>
</template>

<style scoped>
.permission-denied-page {
  justify-content: center;
}
</style>
