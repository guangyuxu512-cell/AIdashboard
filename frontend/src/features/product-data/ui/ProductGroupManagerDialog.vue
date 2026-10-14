<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NAlert, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { AppButton, AppDialog, AppInput } from '@/shared/ui'
import { EmptyState, ErrorState, LoadingState } from '@/shared/components'
import { productDataKeys } from '../api/query-keys'
import { productGroupNameSchema } from '../model/query'
import type { ProductDataSource, ProductGroup } from '../model/types'

const props = defineProps<{
  show: boolean
  shopId: string
  contextKey: string
  source: ProductDataSource
}>()
const emit = defineEmits<{
  'update:show': [show: boolean]
  deleted: [groupId: string]
}>()
const queryClient = useQueryClient()
const editingId = ref<string | null>(null),
  deleting = ref<ProductGroup | null>(null),
  error = ref<string | null>(null)
const { defineField, resetForm, handleSubmit, setFieldError, errors } =
  useForm<{ name: string }>({ initialValues: { name: '' } })
const [name] = defineField('name')
let revision = 0
watch(
  () => [props.show, props.shopId],
  () => {
    revision++
    resetForm({ values: { name: '' } })
    editingId.value = null
    deleting.value = null
    error.value = null
  },
)
const groups = useQuery({
  queryKey: computed(() =>
    productDataKeys.groups(props.contextKey, props.shopId),
  ),
  enabled: computed(() => props.show && props.source.available),
  queryFn: () => props.source.groups(props.shopId),
  retry: false,
})
const saveMutation = useMutation({
  mutationFn: (input: { id: string | null; name: string; shopId: string }) =>
    props.source.saveGroup(input.shopId, input),
})
const deleteMutation = useMutation({
  mutationFn: (input: { shopId: string; groupId: string }) =>
    props.source.deleteGroup(input.shopId, input.groupId),
})
function edit(group: ProductGroup) {
  editingId.value = group.id
  resetForm({ values: { name: group.name } })
  error.value = null
}
function cancelEdit() {
  editingId.value = null
  resetForm({ values: { name: '' } })
  error.value = null
}
function requestDelete(group: ProductGroup) {
  deleting.value = group
  error.value = null
}
function closeDelete() {
  deleting.value = null
  error.value = null
}
const save = handleSubmit(async (values) => {
  if (saveMutation.isPending.value || deleteMutation.isPending.value) return
  const parsed = productGroupNameSchema.safeParse(values.name)
  if (!parsed.success) {
    setFieldError('name', parsed.error.issues[0]?.message)
    return
  }
  const generation = revision,
    shopId = props.shopId,
    contextKey = props.contextKey
  error.value = null
  try {
    await saveMutation.mutateAsync({
      id: editingId.value,
      name: parsed.data,
      shopId,
    })
    await queryClient.invalidateQueries({
      queryKey: productDataKeys.all(contextKey),
    })
    if (generation === revision) cancelEdit()
  } catch (cause) {
    if (generation === revision)
      error.value =
        cause instanceof Error ? cause.message : '分组保存失败，请重试'
  }
})
async function confirmDelete() {
  if (!deleting.value || deleteMutation.isPending.value) return
  const group = deleting.value,
    generation = revision,
    shopId = props.shopId,
    contextKey = props.contextKey
  error.value = null
  try {
    await deleteMutation.mutateAsync({ shopId, groupId: group.id })
    await queryClient.invalidateQueries({
      queryKey: productDataKeys.all(contextKey),
    })
    if (generation === revision) {
      deleting.value = null
      if (editingId.value === group.id) cancelEdit()
      emit('deleted', group.id)
    }
  } catch (cause) {
    if (generation === revision)
      error.value =
        cause instanceof Error ? cause.message : '分组删除失败，请重试'
  }
}
</script>

<template>
  <AppDialog
    :show="show"
    title="分组管理"
    positive-text="完成"
    :show-negative="false"
    @confirm="$emit('update:show', false)"
    @update:show="$emit('update:show', $event)"
  >
    <div class="product-groups">
      <NForm label-placement="top" @submit.prevent="save">
        <NFormItem
          :label="editingId ? '重命名分组' : '新建分组'"
          :feedback="errors.name"
          :validation-status="errors.name ? 'error' : undefined"
        >
          <div class="product-groups__editor">
            <AppInput
              v-model="name"
              aria-label="分组名称"
              placeholder="例如：出单款"
              :maxlength="40"
              :disabled="saveMutation.isPending.value"
            />
            <AppButton
              tone="primary"
              :loading="saveMutation.isPending.value"
              :disabled="deleteMutation.isPending.value"
              @click="save"
              >{{ editingId ? '保存名称' : '创建分组' }}</AppButton
            >
            <AppButton v-if="editingId" @click="cancelEdit">取消编辑</AppButton>
          </div>
        </NFormItem>
      </NForm>
      <NAlert v-if="error && !deleting" type="error" :show-icon="false">{{
        error
      }}</NAlert>
      <LoadingState v-if="groups.isPending.value" />
      <ErrorState
        v-else-if="groups.error.value"
        description="分组读取失败"
        retryable
        @retry="groups.refetch()"
      />
      <EmptyState
        v-else-if="!groups.data.value?.length"
        description="暂无分组"
      />
      <div v-else class="product-groups__list">
        <div
          v-for="group in groups.data.value"
          :key="group.id"
          class="product-groups__row"
        >
          <span class="product-groups__name" :title="group.name">{{
            group.name
          }}</span>
          <span class="product-groups__count">{{ group.productCount }} 件</span>
          <AppButton
            tone="text"
            size="small"
            :disabled="
              saveMutation.isPending.value || deleteMutation.isPending.value
            "
            @click="edit(group)"
            >重命名</AppButton
          >
          <AppButton
            tone="danger"
            size="small"
            :disabled="
              saveMutation.isPending.value || deleteMutation.isPending.value
            "
            @click="requestDelete(group)"
            >删除</AppButton
          >
        </div>
      </div>
    </div>
  </AppDialog>
  <AppDialog
    :show="!!deleting"
    title="删除商品分组"
    positive-text="删除"
    :loading="deleteMutation.isPending.value"
    @confirm="confirmDelete"
    @update:show="closeDelete"
  >
    <p>
      删除“{{ deleting?.name }}”后，{{ deleting?.productCount ?? 0 }}
      件商品将移至未分组，商品和指标保留。
    </p>
    <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
  </AppDialog>
</template>

<style scoped>
.product-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.product-groups__editor {
  display: flex;
  width: 100%;
  gap: var(--space-2);
}
.product-groups__editor > :first-child {
  flex: 1;
}
.product-groups__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.product-groups__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}
.product-groups__name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.product-groups__count {
  color: var(--text-secondary);
}
</style>
