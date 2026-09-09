import { describe, expect, it } from 'vitest'

import aiNavigationSource from '../../ui/AiModuleNavigation.vue?raw'
import materialRoleTabsSource from '../../assets/ui/MaterialRoleTabs.vue?raw'
import batchSource from './BatchGenerationPanel.vue?raw'
import batchViewerSource from './BatchExecutionViewer.vue?raw'
import batchPickerSource from './BatchProductPickerDialog.vue?raw'
import batchProductTaskRowSource from './BatchProductTaskRow.vue?raw'
import batchTemplateCardSource from './BatchTemplateExecutionCard.vue?raw'
import inputSlotSource from './GenerationInputSlot.vue?raw'
import instantResultCardSource from './InstantResultCard.vue?raw'
import instantResultViewerSource from './InstantResultViewer.vue?raw'
import instantSummarySource from './InstantExecutionSummary.vue?raw'
import instantSource from './InstantGenerationPanel.vue?raw'
import generatePageSource from '../../../../pages/ai-workbench/AiGeneratePage.vue?raw'
import generationRealSource from './AiGenerationReal.vue?raw'
import generationVisualMockSource from './AiGenerationVisualMock.vue?raw'

function occurrences(source: string, value: string): number {
  return source.split(value).length - 1
}

describe('AI generation shared control reuse contracts', () => {
  it('uses the same ContextSwitchBar component as AI module navigation', () => {
    expect(aiNavigationSource).toContain(
      "import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'",
    )
    expect(instantSource).toContain(
      "import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'",
    )
    expect(batchSource).toContain(
      "import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'",
    )
    expect(generationRealSource).toContain(
      "import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'",
    )
    expect(generationVisualMockSource).toContain(
      "import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'",
    )

    expect(occurrences(instantSource, '<ContextSwitchBar')).toBe(2)
    expect(occurrences(batchSource, '<ContextSwitchBar')).toBe(4)
    expect(occurrences(generationRealSource, '<ContextSwitchBar')).toBe(1)
    expect(occurrences(generationVisualMockSource, '<ContextSwitchBar')).toBe(1)
    expect(occurrences(instantSource, 'appearance="bare"')).toBe(2)
    expect(occurrences(batchSource, 'appearance="bare"')).toBe(4)
    expect(occurrences(generationRealSource, 'appearance="bare"')).toBe(1)
    expect(occurrences(generationVisualMockSource, 'appearance="bare"')).toBe(1)
    expect(aiNavigationSource).not.toContain('appearance="bare"')
    expect(
      `${instantSource}${batchSource}${generationRealSource}${generationVisualMockSource}`,
    ).not.toContain('AppRadio')
  })

  it('uses the shared bare appearance instead of feature frame overrides', () => {
    expect(materialRoleTabsSource).toContain('appearance="bare"')
    expect(materialRoleTabsSource).not.toContain('border: 0')
    expect(materialRoleTabsSource).not.toContain('background: transparent')
    expect(
      `${instantSource}${batchSource}${generationRealSource}${generationVisualMockSource}`,
    ).not.toMatch(/context-switch-bar[\s\S]*(border|background|border-radius)/)
    expect(generatePageSource).toContain('AiGenerationReal')
  })

  it('covers every required short value selector with the shared contract', () => {
    for (const label of [
      '生成模式',
      '输出格式',
      '批量生成模式',
      '产品范围',
      '模板来源',
      '输出范围',
    ]) {
      expect(`${instantSource}${batchSource}`).toContain(`label="${label}"`)
    }
    expect(batchSource).toContain('产品已配置')
    expect(batchSource).toContain('本次选择')
    expect(batchSource).not.toContain('模板策略')
  })

  it('keeps the product list at four shared rows with internal scrolling', () => {
    expect(batchSource).toContain('CompactEntityRow')
    expect(batchSource).toContain('data-testid="batch-product-list"')
    expect(batchSource).toMatch(
      /var\(--table-list-row-slot-height\) \* 4[\s\S]*overflow-y: auto/,
    )
    expect(batchSource).toContain('<Folder :size="16"')
    expect(batchPickerSource).toContain('CompactEntityRow')
    expect(batchPickerSource).toContain('AppCheckbox')
    expect(batchPickerSource).toContain('PaginationBar')
  })

  it('uses Naive Upload for the complete input surface without an upload button', () => {
    expect(inputSlotSource).toContain('NUpload')
    expect(inputSlotSource).toContain('NUploadDragger')
    expect(inputSlotSource).not.toContain(['<', 'input'].join(''))
    expect(inputSlotSource).not.toContain('fileInput')
    expect(inputSlotSource).not.toContain('ImageUp')
  })

  it('composes the batch viewer from formal progress, collapse and project controls', () => {
    expect(batchViewerSource).toContain('NProgress')
    expect(batchViewerSource).toContain('NCollapse')
    expect(batchViewerSource).toContain('NCollapseItem')
    expect(batchViewerSource).toContain('ContextSwitchBar')
    expect(batchViewerSource).toContain('appearance="bare"')
    expect(batchViewerSource).toContain('AppDialog')
    expect(batchViewerSource).toContain('StatusTag')
    expect(batchProductTaskRowSource).toContain('CompactEntityRow')
    expect(batchProductTaskRowSource).toContain('NProgress')
    expect(batchTemplateCardSource).toContain('AssetContentImage')
    expect(batchTemplateCardSource).toContain('NSpin')
    expect(batchTemplateCardSource).toContain('AppButton')
    expect(batchTemplateCardSource).toContain('StatusTag')
    expect(batchTemplateCardSource).toContain('已归档')
    expect(batchTemplateCardSource).not.toContain('保存到素材库')
    expect(batchSource).toContain('batch-preflight__header')
    expect(batchSource).toContain('查看问题')
    expect(batchViewerSource).not.toContain('<details')
  })

  it('composes the instant viewer from formal progress, preview and state controls', () => {
    expect(instantSource).toContain('InstantResultViewer')
    expect(instantResultViewerSource).toContain('EmptyState')
    expect(instantSummarySource).toContain('NProgress')
    expect(instantSummarySource).toContain('StatusTag')
    expect(instantSummarySource).toContain('AppButton')
    expect(instantResultCardSource).toContain('AssetContentImage')
    expect(instantResultCardSource).toContain('NSpin')
    expect(instantResultCardSource).toContain('NDropdown')
    expect(instantResultCardSource).toContain('StatusTag')
    expect(instantResultCardSource).toContain('AppButton')
    expect(instantResultCardSource).toContain('保存到素材库')
    expect(instantResultCardSource).not.toContain('<img')
    expect(instantResultCardSource).not.toContain('<button')
    expect(instantResultViewerSource).not.toContain('Product')
    expect(instantResultViewerSource).not.toContain('Template')
  })

  it('keeps one visible editable config and a clearable template select', () => {
    expect(instantSource).toContain('data-testid="instant-generation-config"')
    expect(instantSource).toContain('aria-label="生成模板"')
    expect(instantSource).toContain('clearable')
    expect(instantSource).not.toContain('GenerationTemplateSummary')
    expect(instantSource).not.toContain('configSource')
  })
})
