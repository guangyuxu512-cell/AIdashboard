import { describe, expect, it } from 'vitest'

import {
  createTimezoneOptions,
  filterTimezoneOption,
  getTimezoneLabel,
} from './timezones'

describe('timezone UI registry', () => {
  it.each([
    ['Asia/Shanghai', '中国标准时间（上海）'],
    ['Asia/Tokyo', '日本标准时间（东京）'],
    ['America/Los_Angeles', '美国太平洋时间（洛杉矶）'],
    ['America/New_York', '美国东部时间（纽约）'],
    ['Europe/London', '英国时间（伦敦）'],
  ])('renders %s with a Chinese label', (timezone, label) => {
    expect(getTimezoneLabel(timezone)).toBe(label)
  })

  it('keeps an additional IANA timezone selectable', () => {
    const options = createTimezoneOptions(['Pacific/Auckland'])
    expect(options.find((option) => option.value === 'Pacific/Auckland')).toEqual(
      expect.objectContaining({
        label: expect.stringContaining('Pacific/Auckland'),
      }),
    )
  })

  it('searches Chinese labels and advanced IANA ids', () => {
    const option = createTimezoneOptions().find(
      (item) => item.value === 'America/Los_Angeles',
    )!
    expect(filterTimezoneOption('洛杉矶', option)).toBe(true)
    expect(filterTimezoneOption('America/Los_Angeles', option)).toBe(true)
  })
})
