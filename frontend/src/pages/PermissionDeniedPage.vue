<script setup lang="ts">
import PermissionDeniedState from '@/shared/components/PermissionDeniedState.vue'
</script>

<template>
  <div class="page-container permission-denied-page">
    <PermissionDeniedState />
  </div>
</template>

<style scoped>
.permission-denied-page {
  display: grid;
  height: 100%;
  min-height: 0;
  place-items: center;
}
</style>
