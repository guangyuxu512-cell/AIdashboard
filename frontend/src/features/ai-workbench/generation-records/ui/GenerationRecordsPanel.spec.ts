import { describe, expect, it } from 'vitest'

import panelSource from './GenerationRecordsPanel.vue?raw'

describe('GenerationRecordsPanel page pattern', () => {
  it('reuses the compact management filter and list primitives', () => {
    expect(panelSource).toContain(
      "import FilterBar from '@/shared/components/FilterBar.vue'",
    )
    expect(panelSource).toContain(
      "import ManagementListSection from '@/shared/components/ManagementListSection.vue'",
    )
    expect(panelSource).toContain('<FilterBar>')
    expect(panelSource).toContain('<ManagementListSection>')
    expect(panelSource).toContain('<PaginationBar')
    expect(panelSource).not.toContain('generation-records-panel__toolbar')
    expect(panelSource).not.toContain('generation-records-panel__table')
  })
})
