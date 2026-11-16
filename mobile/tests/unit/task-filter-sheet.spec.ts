import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createDefaultTaskFilterDraft,
  TaskFilterSheet,
  type TaskFilterDraft,
} from '@/features/task-center'

const mountedWrappers: VueWrapper[] = []
const now = new Date(2026, 7, 26, 12, 0, 0)

function mountSheet(
  filters: TaskFilterDraft = createDefaultTaskFilterDraft(now),
) {
  const wrapper = mount(TaskFilterSheet, {
    props: { modelValue: true, filters },
    attachTo: document.body,
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('task run-date filter sheet', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(now)
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount()
    document.body.innerHTML = ''
    vi.useRealTimers()
  })

  it('offers only the four confirmed quick presets and no legacy device filter', () => {
    const wrapper = mountSheet()

    expect(
      wrapper
        .findAll('[data-testid^="task-date-preset-"]')
        .map((button) => button.text()),
    ).toEqual(['今天', '昨天', '近7天', '全部'])
    expect(wrapper.text()).not.toContain('设备')
    expect(wrapper.find('[data-testid="device-filter"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="task-date-range"]').exists()).toBe(false)
  })

  it('applies a quick preset immediately and closes the sheet', async () => {
    const wrapper = mountSheet()
    await wrapper.get('[data-testid="task-date-preset-today"]').trigger('click')

    const applied = wrapper.emitted('apply')?.[0]?.[0] as TaskFilterDraft
    expect(applied.datePreset).toBe('today')
    expect(applied.dateRange).toEqual([
      new Date(2026, 7, 26),
      new Date(2026, 7, 26),
    ])
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })

  it('restores and applies one custom local date instead of a range', async () => {
    const customDate = new Date(2026, 7, 18)
    const wrapper = mountSheet({
      search: '',
      datePreset: 'custom',
      dateRange: [customDate, customDate],
    })
    const input = wrapper.get<HTMLInputElement>(
      '[data-testid="task-custom-date"]',
    )

    expect(input.element.value).toBe('2026-08-18')
    await input.setValue('2026-08-21')
    await wrapper.get('[data-testid="apply-task-custom-date"]').trigger('click')

    const applied = wrapper.emitted('apply')?.[0]?.[0] as TaskFilterDraft
    expect(applied.datePreset).toBe('custom')
    expect(applied.dateRange).toEqual([
      new Date(2026, 7, 21),
      new Date(2026, 7, 21),
    ])
  })
})
