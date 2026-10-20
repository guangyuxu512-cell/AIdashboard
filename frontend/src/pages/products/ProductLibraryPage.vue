<script setup lang="ts">
import { apiMode } from '@/shared/api'
import { StatusTag } from '@/shared/components'
import ProductLibraryWorkspace from '@/features/product-library/ui/ProductLibraryWorkspace.vue'
</script>

<template>
  <div class="page-container product-library-page">
    <div v-if="apiMode === 'mock'" class="product-library-page__mode">
      <StatusTag label="演示数据" />
    </div>
    <ProductLibraryWorkspace />
  </div>
</template>

<style scoped>
.product-library-page {
  height: 100%;
  min-height: 0;
}
.product-library-page__mode {
  display: flex;
  justify-content: flex-end;
}
</style>
