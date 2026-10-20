<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NList, NListItem, NText } from 'naive-ui'
import { AppButton, AppDialog, AppRadio, AppSelect } from '@/shared/ui'
import type { ProductGroup } from '../model/contracts'

const props = defineProps<{ show: boolean; groups: ProductGroup[] }>()
defineEmits<{
  'update:show': [value: boolean]
  confirm: [payload: { files: File[]; groupId: string | null; mode: string }]
}>()

const mode = ref<'txt' | 'zip' | 'folder'>('txt')
const files = ref<File[]>([])
const groupId = ref<string | null>(null)
const txtInput = ref<HTMLInputElement | null>(null)
const zipInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const modeOptions = [
  { label: 'TXT 文件', value: 'txt' },
  { label: 'ZIP 包', value: 'zip' },
  { label: '文件夹', value: 'folder' },
]
const groupOptions = computed(() => [
  { label: '未分组', value: 'ungrouped' },
  ...props.groups.map((group) => ({ label: group.name, value: group.id })),
])

watch(
  () => props.show,
  (show) => {
    if (!show) return
    mode.value = 'txt'
    files.value = []
    groupId.value = null
  },
)

function chooseFiles() {
  if (mode.value === 'txt') txtInput.value?.click()
  else if (mode.value === 'zip') zipInput.value?.click()
  else folderInput.value?.click()
}

function selected(event: Event) {
  const input = event.target as HTMLInputElement
  files.value = [...(input.files ?? [])]
  input.value = ''
}
</script>

<template>
  <AppDialog
    :show="show"
    title="导入商品资料包"
    size="md"
    positive-text="确认演示"
    :positive-disabled="!files.length"
    positive-disabled-reason="请先选择 TXT、ZIP 或文件夹"
    @update:show="$emit('update:show', $event)"
    @confirm="
      $emit('confirm', {
        files,
        groupId,
        mode,
      })
    "
  >
    <div class="product-import-dialog__controls">
      <AppRadio v-model="mode" :options="modeOptions" />
      <AppSelect
        :model-value="groupId ?? 'ungrouped'"
        :options="groupOptions"
        width="md"
        @update:model-value="
          (value) => (groupId = value === 'ungrouped' ? null : String(value))
        "
      />
      <input
        ref="txtInput"
        class="product-import-dialog__input"
        type="file"
        accept=".txt,text/plain"
        multiple
        @change="selected"
      />
      <input
        ref="zipInput"
        class="product-import-dialog__input"
        type="file"
        accept=".zip,application/zip"
        multiple
        @change="selected"
      />
      <input
        ref="folderInput"
        class="product-import-dialog__input"
        type="file"
        multiple
        webkitdirectory=""
        directory=""
        @change="selected"
      />
      <AppButton @click="chooseFiles"
        >选择{{
          modeOptions.find((item) => item.value === mode)?.label
        }}</AppButton
      >
    </div>
    <NList v-if="files.length" bordered class="product-import-dialog__files">
      <NListItem v-for="file in files" :key="`${file.name}:${file.size}`">
        {{ file.webkitRelativePath || file.name }} · {{ file.size }} B
      </NListItem>
    </NList>
    <NText v-else depth="3">尚未选择文件。</NText>
    <NText depth="3">
      演示模式仅验证选择、文件清单和目标分组，不解析
      ZIP、清洗文本或写入正式商品库。
    </NText>
  </AppDialog>
</template>

<style scoped>
.product-import-dialog__controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.product-import-dialog__input {
  display: none;
}
.product-import-dialog__files {
  max-height: 240px;
  margin-bottom: var(--space-3);
  overflow: auto;
}
</style>
