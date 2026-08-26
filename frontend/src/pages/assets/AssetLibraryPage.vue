<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'

import {
  AssetDeleteDialog,
  AssetListTable,
  useAssetManagement,
} from '@/features/asset-management'
import { getErrorMessage } from '@/shared/api'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppButton, AppInput } from '@/shared/ui'

const management = useAssetManagement()
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)

function chooseFiles(): void {
  fileInput.value?.click()
}

async function uploadFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  if (!files.length) return
  try {
    for (const file of files) {
      await management.uploadMutation.mutateAsync(file)
    }
    message.success(`已上传 ${files.length} 张图片`)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function confirmDelete(): Promise<void> {
  const asset = management.deletingAsset.value
  if (!asset) return
  try {
    await management.deleteMutation.mutateAsync(asset.assetId)
    management.deletingAsset.value = null
    message.success('图片已删除')
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <div class="page-container asset-library-page">
    <FilterBar>
      <AppInput
        v-model="management.searchDraft.value"
        placeholder="搜索图片文件名"
        width="lg"
        clearable
        @keyup.enter="management.query"
      />
      <template #actions>
        <AppButton @click="management.reset">重置</AppButton>
        <AppButton tone="primary" @click="management.query">查询</AppButton>
      </template>
      <template #primary-action>
        <input
          ref="fileInput"
          class="asset-library-page__file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          @change="uploadFiles"
        />
        <AppButton
          tone="primary"
          :loading="management.uploadMutation.isPending.value"
          @click="chooseFiles"
        >
          + 上传图片
        </AppButton>
      </template>
    </FilterBar>

    <ManagementListSection>
      <AssetListTable
        :rows="management.rows.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        @remove="management.deletingAsset.value = $event"
        @retry="management.retry"
      />
      <PaginationBar
        v-model:page="management.page.value"
        :page-size="management.pageSize.value"
        :item-count="management.total.value"
        @update:page-size="management.setPageSize"
      />
    </ManagementListSection>

    <AssetDeleteDialog
      :show="Boolean(management.deletingAsset.value)"
      :asset="management.deletingAsset.value"
      :loading="management.deleteMutation.isPending.value"
      @update:show="management.deletingAsset.value = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.asset-library-page {
  height: 100%;
  min-height: 0;
}

.asset-library-page__file-input {
  display: none;
}
</style>
