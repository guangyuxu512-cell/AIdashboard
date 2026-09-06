import { describe, expect, it } from 'vitest'

import type { AiModelCreateInput } from '../model/types'
import { createAiModelDataSource } from './ai-model-data-source'

const newModel: AiModelCreateInput = {
  displayName: 'Next Image Model',
  modelCode: 'next-image-model',
  providerCode: 'toapis',
  enabled: true,
  isDefault: false,
  capabilities: ['NORMAL_GENERATION'],
  maxInputImages: 2,
  supportedSizes: ['1:1', '3:4'],
  supportedResolutions: ['1k'],
}

describe('AI model data source', () => {
  it('starts with the real GPT Image 2 capability facts', async () => {
    const source = createAiModelDataSource('mock')

    await expect(source.list()).resolves.toMatchObject([
      {
        displayName: 'GPT Image 2',
        modelCode: 'gpt-image-2',
        providerCode: 'toapis',
        enabled: true,
        isDefault: true,
        capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
        maxInputImages: 6,
        supportedSizes: ['1:1', '3:4', '4:3', '16:9'],
        supportedResolutions: ['1k', '2k', '4k'],
      },
    ])
  })

  it('creates, edits, switches default, and toggles enabled state', async () => {
    const source = createAiModelDataSource('mock')
    const [initial] = await source.list()
    const created = await source.create(newModel)
    const edited = await source.update(created.modelId, {
      displayName: 'Updated Image Model',
      enabled: true,
      isDefault: false,
      capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
      maxInputImages: 4,
      supportedSizes: ['1:1', '16:9'],
      supportedResolutions: ['1k', '2k'],
    })

    expect(edited).toMatchObject({
      modelCode: 'next-image-model',
      providerCode: 'toapis',
      displayName: 'Updated Image Model',
      maxInputImages: 4,
    })

    await source.setDefault(created.modelId)
    await source.update(initial!.modelId, {
      displayName: initial!.displayName,
      enabled: false,
      isDefault: false,
      capabilities: initial!.capabilities,
      maxInputImages: initial!.maxInputImages,
      supportedSizes: initial!.supportedSizes,
      supportedResolutions: initial!.supportedResolutions,
    })
    const models = await source.list()

    expect(models.filter((model) => model.isDefault)).toHaveLength(1)
    expect(
      models.find((model) => model.modelId === created.modelId),
    ).toMatchObject({ isDefault: true, enabled: true })
    expect(
      models.find((model) => model.modelId === initial!.modelId)?.enabled,
    ).toBe(false)
  })

  it('rejects disabling the current default and contains no secret fields', async () => {
    const source = createAiModelDataSource('mock')
    const [initial] = await source.list()

    await expect(
      source.update(initial!.modelId, {
        displayName: initial!.displayName,
        enabled: false,
        isDefault: true,
        capabilities: initial!.capabilities,
        maxInputImages: initial!.maxInputImages,
        supportedSizes: initial!.supportedSizes,
        supportedResolutions: initial!.supportedResolutions,
      }),
    ).rejects.toThrow('请先设置另一个已启用模型为默认模型')

    const serialized = JSON.stringify(await source.list())
    expect(serialized).not.toContain('apiKey')
    expect(serialized).not.toContain('baseUrl')
    expect(serialized).not.toContain('secret')
  })
})
