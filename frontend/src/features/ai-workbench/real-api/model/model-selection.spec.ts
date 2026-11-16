import { describe, expect, it } from 'vitest'

import type { WorkbenchModelView } from './mappers'
import {
  compatibleWorkbenchModels,
  isWorkbenchModelInputCountAllowed,
  isWorkbenchModelSizeSupported,
  remainingWorkbenchModelInputCapacity,
  resolveWorkbenchModelId,
} from './model-selection'

const models: WorkbenchModelView[] = [
  {
    id: 'normal-model',
    code: 'normal',
    name: '普通模型',
    capabilities: ['NORMAL_GENERATION'],
    maxInputImages: 2,
    supportedSizes: ['1:1'],
    supportedResolutions: ['1k'],
    isDefault: false,
  },
  {
    id: 'default-model',
    code: 'both',
    name: '默认模型',
    capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
    maxInputImages: 6,
    supportedSizes: ['1:1', '3:4'],
    supportedResolutions: ['1k'],
    isDefault: true,
  },
]

describe('AI Workbench model selection', () => {
  it('filters the model catalog by generation capability', () => {
    expect(
      compatibleWorkbenchModels(models, 'STYLE_REPLICATION').map(
        (model) => model.id,
      ),
    ).toEqual(['default-model'])
    expect(
      compatibleWorkbenchModels(models, 'NORMAL_GENERATION').map(
        (model) => model.id,
      ),
    ).toEqual(['normal-model', 'default-model'])
  })

  it('selects the compatible default and preserves an explicit compatible choice', () => {
    expect(resolveWorkbenchModelId(models, 'NORMAL_GENERATION', null)).toBe(
      'default-model',
    )
    expect(
      resolveWorkbenchModelId(models, 'NORMAL_GENERATION', 'normal-model'),
    ).toBe('normal-model')
    expect(
      resolveWorkbenchModelId(models, 'STYLE_REPLICATION', 'normal-model'),
    ).toBe('default-model')
  })

  it('enforces the catalog input limit without allowing negative counts', () => {
    expect(isWorkbenchModelInputCountAllowed(models[0]!, 2)).toBe(true)
    expect(isWorkbenchModelInputCountAllowed(models[0]!, 3)).toBe(false)
    expect(isWorkbenchModelInputCountAllowed(models[0]!, -1)).toBe(false)
    expect(isWorkbenchModelInputCountAllowed(null, 0)).toBe(false)
    expect(remainingWorkbenchModelInputCapacity(null, 0)).toBeNull()
    expect(remainingWorkbenchModelInputCapacity(models[0]!, 1)).toBe(1)
    expect(remainingWorkbenchModelInputCapacity(models[0]!, 4)).toBe(0)
  })

  it('accepts only sizes declared by the selected catalog model', () => {
    expect(isWorkbenchModelSizeSupported(models[0]!, '1:1')).toBe(true)
    expect(isWorkbenchModelSizeSupported(models[0]!, '3:4')).toBe(false)
    expect(isWorkbenchModelSizeSupported(null, '1:1')).toBe(false)
  })
})
