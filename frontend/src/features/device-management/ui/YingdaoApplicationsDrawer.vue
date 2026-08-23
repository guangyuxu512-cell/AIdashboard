<script setup lang="ts">
import type { ProviderApplicationViewModel } from '@/entities/device'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import YingdaoApplicationsTable from './YingdaoApplicationsTable.vue'

defineProps<{
  show: boolean
  applications: ProviderApplicationViewModel[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  configure: [application: ProviderApplicationViewModel]
  run: [application: ProviderApplicationViewModel]
}>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="影刀应用列表"
    size="lg"
    @update:show="$emit('update:show', $event)"
  >
    <p class="yingdao-applications__description">
      当前设备 6.3.6 登录账号可访问的云端应用。参数配置属于中控台配置，运行将创建正式 Task。
    </p>
    <YingdaoApplicationsTable
      :applications="applications"
      @configure="emit('configure', $event)"
      @run="emit('run', $event)"
    />

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.yingdao-applications__description {
  margin-bottom: var(--space-4);
  color: var(--color-text-secondary);
}

</style>
