<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NAlert } from 'naive-ui'
import { AppDialog, AppSelect } from '@/shared/ui'
import { ErrorState } from '@/shared/components'
import { productDataKeys } from '../api/query-keys'
import type { ProductDataRow, ProductDataSource } from '../model/types'

const props = defineProps<{
  show: boolean
  shopId: string
  rows: ProductDataRow[]
  contextKey: string
  source: ProductDataSource
}>()
const emit = defineEmits<{ 'update:show': [show: boolean]; saved: [] }>()
const groupId = ref<string | null>(null),
  error = ref<string | null>(null)
const queryClient = useQueryClient()
let revision = 0
watch(
  () => [props.show, props.shopId],
  () => {
    revision++
    groupId.value = null
    error.value = null
  },
)
const groups = useQuery({
  queryKey: computed(() =>
    productDataKeys.groups(props.contextKey, props.shopId),
  ),
  queryFn: () => props.source.groups(props.shopId),
  enabled: computed(() => props.show && props.source.available),
  retry: false,
})
const options = computed(() => [
  { label: '移出分组', value: 'ungrouped' },
  ...(groups.data.value ?? []).map((group) => ({
    label: group.name,
    value: group.id,
  })),
])
const mutation = useMutation({
  mutationFn: (input: {
    shopId: string
    ids: string[]
    groupId: string | null
  }) => props.source.assignGroup(input.shopId, input.ids, input.groupId),
})
async function save() {
  if (mutation.isPending.value || groupId.value === null) return
  if (
    !props.rows.length ||
    props.rows.some((row) => row.shopId !== props.shopId)
  ) {
    error.value = '只能设置同一店铺的商品分组'
    return
  }
  const generation = revision,
    contextKey = props.contextKey
  error.value = null
  try {
    await mutation.mutateAsync({
      shopId: props.shopId,
      ids: props.rows.map((row) => row.id),
      groupId: groupId.value === 'ungrouped' ? null : groupId.value,
    })
    await queryClient.invalidateQueries({
      queryKey: productDataKeys.all(contextKey),
    })
    if (generation === revision) {
      emit('saved')
      emit('update:show', false)
    }
  } catch (cause) {
    if (generation === revision)
      error.value =
        cause instanceof Error ? cause.message : '设置分组失败，请重试'
  }
}
</script>

<template>
  <AppDialog
    :show="show"
    title="批量设置分组"
    positive-text="保存"
    :loading="mutation.isPending.value"
    :positive-disabled="
      groupId === null ||
      groups.isPending.value ||
      !!groups.error.value ||
      !rows.length
    "
    @confirm="save"
    @update:show="$emit('update:show', $event)"
  >
    <div class="product-batch-group">
      <p>{{ rows[0]?.shopName }} · 已选 {{ rows.length }} 件商品</p>
      <ErrorState
        v-if="groups.error.value"
        description="分组读取失败"
        retryable
        @retry="groups.refetch()"
      />
      <AppSelect
        v-else
        :model-value="groupId"
        :options="options"
        :loading="groups.isPending.value"
        placeholder="选择分组或移出"
        @update:model-value="groupId = $event === null ? null : String($event)"
      />
      <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
    </div>
  </AppDialog>
</template>

<style scoped>
.product-batch-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.product-batch-group p {
  margin: 0;
  color: var(--text-secondary);
}
</style>
