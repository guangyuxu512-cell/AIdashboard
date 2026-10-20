<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AppButton, AppDialog, AppInput, AppSelect } from '@/shared/ui'
import type { ProductGroup } from '../model/contracts'

const props = defineProps<{
  show: boolean
  groups: ProductGroup[]
  count: number
  loading?: boolean
  title?: string
}>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [groupId: string | null]
  create: [name: string]
}>()
const selected = ref<string | null>(null)
const newName = ref('')
const options = computed(() => [
  { label: '未分组', value: 'ungrouped' },
  ...props.groups.map((group) => ({
    label: `${group.name}（${group.count}）`,
    value: group.id,
  })),
])
watch(
  () => props.show,
  (show) => {
    if (show) {
      selected.value = null
      newName.value = ''
    }
  },
)

function createGroup() {
  const name = newName.value.trim()
  if (!name) return
  emit('create', name)
  newName.value = ''
}
</script>

<template>
  <AppDialog
    :show="show"
    :title="title ?? '移动商品分组'"
    size="sm"
    positive-text="确认移动"
    :loading="loading"
    :positive-disabled="count === 0"
    positive-disabled-reason="请先选择商品"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('confirm', selected)"
  >
    <div class="product-group-dialog__stack">
      <AppSelect
        :model-value="selected ?? 'ungrouped'"
        :options="options"
        @update:model-value="
          (value) => (selected = value === 'ungrouped' ? null : String(value))
        "
      />
      <div class="product-group-dialog__create">
        <AppInput v-model="newName" placeholder="新分组名称" :maxlength="40" />
        <AppButton :disabled="!newName.trim()" @click="createGroup"
          >新建分组</AppButton
        >
      </div>
    </div>
  </AppDialog>
</template>

<style scoped>
.product-group-dialog__stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.product-group-dialog__create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}
</style>
