<script setup lang="ts">
import { NButton } from 'naive-ui'

export type AppButtonTone = 'primary' | 'secondary' | 'danger' | 'text'

withDefaults(
  defineProps<{
    tone?: AppButtonTone
    loading?: boolean
    disabled?: boolean
    block?: boolean
    attrType?: 'button' | 'submit' | 'reset'
  }>(),
  {
    tone: 'secondary',
    loading: false,
    disabled: false,
    block: false,
    attrType: 'button',
  },
)

defineEmits<{
  click: [event: MouseEvent]
}>()
</script>

<template>
  <NButton
    size="medium"
    :type="tone === 'primary' ? 'primary' : tone === 'danger' ? 'error' : 'default'"
    :quaternary="tone === 'text'"
    :loading="loading"
    :disabled="disabled"
    :block="block"
    :attr-type="attrType"
    @click="$emit('click', $event)"
  >
    <slot />
  </NButton>
</template>
