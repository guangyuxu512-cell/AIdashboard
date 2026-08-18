<script setup lang="ts">
import { NConfigProvider, NGlobalStyle, NMessageProvider } from 'naive-ui'
import { RouterView } from 'vue-router'

import { naiveThemeOverrides } from '@/app/providers/naive-theme'
</script>

<template>
  <NConfigProvider :theme-overrides="naiveThemeOverrides">
    <NGlobalStyle />
    <NMessageProvider>
      <RouterView />
    </NMessageProvider>
  </NConfigProvider>
</template>
