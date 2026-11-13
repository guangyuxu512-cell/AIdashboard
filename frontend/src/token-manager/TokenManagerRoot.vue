<script setup lang="ts">
import { dateZhCN, NConfigProvider, NGlobalStyle, NMessageProvider, zhCN } from 'naive-ui'

import TokenManager from './TokenManager.vue'
</script>

<template>
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN">
    <NGlobalStyle />
    <NMessageProvider><TokenManager /></NMessageProvider>
  </NConfigProvider>
</template>
