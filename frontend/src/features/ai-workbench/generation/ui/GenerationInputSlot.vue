<script setup lang="ts">
import { Images, X } from '@lucide/vue'
import { NUpload, NUploadDragger } from 'naive-ui'
import type { UploadSettledFileInfo } from 'naive-ui'

import { AssetContentImage } from '@/entities/asset'
import EmptyState from '@/shared/components/EmptyState.vue'
import { AppButton } from '@/shared/ui'

import type { GenerationInputSlotDefinition } from '../model/generation-mode-registry'
import type { GenerationSourceImageView } from '../model/types'

defineProps<{
  definition: GenerationInputSlotDefinition
  images: GenerationSourceImageView[]
}>()

const emit = defineEmits<{
  upload: [files: File[]]
  select: []
  remove: [sourceId: string]
}>()

function upload({ file }: { file: UploadSettledFileInfo }): boolean {
  if (file.file) emit('upload', [file.file])
  return false
}
</script>

<template>
  <section
    class="generation-input-slot"
    :data-input-slot="definition.key"
    :aria-label="definition.label"
  >
    <header class="generation-input-slot__header">
      <strong>{{ definition.label }}</strong>
      <div class="generation-input-slot__actions">
        <AppButton
          v-if="definition.allowMaterialLibrary"
          tone="text"
          @click="$emit('select')"
        >
          <Images :size="15" />
          素材库
        </AppButton>
      </div>
    </header>

    <NUpload
      v-if="definition.allowLocalUpload"
      class="generation-input-slot__upload"
      accept="image/jpeg,image/png,image/webp"
      multiple
      :show-file-list="false"
      :input-props="{ 'aria-label': `上传${definition.label}` }"
      :on-before-upload="upload"
    >
      <NUploadDragger
        class="generation-input-slot__surface"
        :aria-label="`点击上传${definition.label}`"
      >
        <div v-if="images.length" class="generation-input-slot__grid">
          <article
            v-for="image in images"
            :key="image.id"
            class="generation-input-slot__image"
            @click.stop
          >
            <span class="generation-input-slot__preview">
              <AssetContentImage
                class="generation-input-slot__content-image"
                :src="image.thumbnailUrl ?? image.previewUrl"
                :alt="image.name"
              />
            </span>
            <span>{{ image.name }}</span>
            <AppButton
              class="generation-input-slot__remove"
              tone="text"
              :aria-label="`移除 ${image.name}`"
              @click.stop="$emit('remove', image.id)"
            >
              <X :size="14" />
            </AppButton>
          </article>
        </div>
        <EmptyState v-else description="点击上传图片" />
      </NUploadDragger>
    </NUpload>
  </section>
</template>

<style scoped>
.generation-input-slot {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.generation-input-slot__header,
.generation-input-slot__actions,
.generation-input-slot__image {
  display: flex;
  min-width: 0;
  align-items: center;
}

.generation-input-slot__header {
  min-height: var(--control-height-default);
  justify-content: space-between;
  gap: var(--space-3);
}

.generation-input-slot__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.generation-input-slot__actions {
  flex: 0 0 auto;
  gap: var(--space-1);
}

.generation-input-slot__upload {
  width: 100%;
}

.generation-input-slot__surface {
  display: grid;
  min-width: 0;
  min-height: calc(var(--control-height-large) * 4 + var(--space-2));
  align-items: stretch;
}

.generation-input-slot__grid {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(auto-fill, minmax(var(--field-width-xs), 1fr));
}

.generation-input-slot__image {
  position: relative;
  align-items: stretch;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-surface-solid);
}

.generation-input-slot__preview {
  display: block;
  width: 100%;
  min-height: 0;
  aspect-ratio: 1;
  overflow: hidden;
}

.generation-input-slot__content-image {
  display: block;
  width: 100%;
  height: 100%;
}

.generation-input-slot__image > span {
  display: block;
  min-width: 0;
  padding: var(--space-2);
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.generation-input-slot__image > :deep(.generation-input-slot__remove) {
  position: absolute;
  top: var(--space-1);
  right: var(--space-1);
}
</style>
