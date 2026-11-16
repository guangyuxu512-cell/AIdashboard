import { describe, expect, it } from 'vitest'

import assetsPageSource from '../../../../pages/ai-workbench/AiAssetLibraryPage.vue?raw'
import generatePageSource from '../../../../pages/ai-workbench/AiGeneratePage.vue?raw'
import recordsPageSource from '../../../../pages/ai-workbench/AiGenerationRecordsPage.vue?raw'
import templatesPageSource from '../../../../pages/ai-workbench/AiTemplateLibraryPage.vue?raw'
import assetsRealSource from '../../assets/ui/AiAssetLibraryReal.vue?raw'
import recordsRealSource from '../../generation-records/ui/GenerationRecordsRealPanel.vue?raw'
import generationRealSource from '../../generation/ui/AiGenerationReal.vue?raw'
import templatesRealSource from '../../templates/ui/AiTemplateLibraryReal.vue?raw'

describe('AI Workbench production data boundary', () => {
  it('renders the Real API implementation by default on every production page', () => {
    for (const source of [
      assetsPageSource,
      generatePageSource,
      recordsPageSource,
      templatesPageSource,
    ]) {
      expect(source).toContain('import.meta.env.DEV')
      expect(source).toContain('defineAsyncComponent')
      expect(source).toContain('visualMockEnabled')
      expect(source).toContain('v-else')
    }
    expect(assetsPageSource).toContain('AiAssetLibraryReal')
    expect(generatePageSource).toContain('AiGenerationReal')
    expect(recordsPageSource).toContain('GenerationRecordsRealPanel')
    expect(templatesPageSource).toContain('AiTemplateLibraryReal')
  })

  it('keeps fixtures and Visual Mock state out of every real implementation', () => {
    const realSources = [
      assetsRealSource,
      generationRealSource,
      recordsRealSource,
      templatesRealSource,
    ].join('\n')

    expect(realSources).not.toContain('__fixtures__')
    expect(realSources).not.toContain('useAiAssetsVisualMock')
    expect(realSources).not.toContain('useAiTemplatesVisualMock')
    expect(realSources).not.toContain('useAiGenerationStore')
    expect(realSources).not.toContain('data:image')
  })

  it('does not keep the unsupported record search interaction in real mode', () => {
    expect(recordsRealSource).not.toContain('搜索生成记录')
    expect(recordsRealSource).not.toContain('searchQuery')
  })
})
