import type { GenerationMode, GenerationSize } from '@/entities/ai-workbench'

import type { WorkbenchModelView } from './mappers'

export function compatibleWorkbenchModels(
  models: WorkbenchModelView[],
  mode: GenerationMode,
): WorkbenchModelView[] {
  return models.filter((model) => model.capabilities.includes(mode))
}

export function resolveWorkbenchModelId(
  models: WorkbenchModelView[],
  mode: GenerationMode,
  currentModelId: string | null,
): string | null {
  const compatible = compatibleWorkbenchModels(models, mode)
  if (compatible.some((model) => model.id === currentModelId)) {
    return currentModelId
  }
  return (
    compatible.find((model) => model.isDefault)?.id ?? compatible[0]?.id ?? null
  )
}

export function isWorkbenchModelInputCountAllowed(
  model: WorkbenchModelView | null,
  inputCount: number,
): boolean {
  return model !== null && inputCount >= 0 && inputCount <= model.maxInputImages
}

export function remainingWorkbenchModelInputCapacity(
  model: WorkbenchModelView | null,
  inputCount: number,
): number {
  return Math.max(0, (model?.maxInputImages ?? 0) - inputCount)
}

export function isWorkbenchModelSizeSupported(
  model: WorkbenchModelView | null,
  size: GenerationSize,
): boolean {
  return model?.supportedSizes.includes(size) ?? false
}
