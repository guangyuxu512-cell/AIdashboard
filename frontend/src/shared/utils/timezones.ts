import type { SelectFilter, SelectOption } from 'naive-ui'

interface TimezoneDefinition {
  value: string
  label: string
  keywords: string
}

interface TimezoneSelectOption extends SelectOption {
  value: string
  label: string
  searchText: string
}

export const COMMON_TIMEZONES: readonly TimezoneDefinition[] = [
  {
    value: 'Asia/Shanghai',
    label: '中国标准时间（上海）',
    keywords: '中国 大陆 北京 上海',
  },
  {
    value: 'Asia/Hong_Kong',
    label: '香港时间',
    keywords: '中国 香港',
  },
  {
    value: 'Asia/Taipei',
    label: '台湾时间（台北）',
    keywords: '中国 台湾 台北',
  },
  {
    value: 'Asia/Tokyo',
    label: '日本标准时间（东京）',
    keywords: '日本 东京',
  },
  {
    value: 'Asia/Seoul',
    label: '韩国标准时间（首尔）',
    keywords: '韩国 首尔',
  },
  {
    value: 'Asia/Singapore',
    label: '新加坡时间',
    keywords: '新加坡',
  },
  {
    value: 'America/Los_Angeles',
    label: '美国太平洋时间（洛杉矶）',
    keywords: '美国 太平洋 洛杉矶',
  },
  {
    value: 'America/Denver',
    label: '美国山地时间（丹佛）',
    keywords: '美国 山地 丹佛',
  },
  {
    value: 'America/Chicago',
    label: '美国中部时间（芝加哥）',
    keywords: '美国 中部 芝加哥',
  },
  {
    value: 'America/New_York',
    label: '美国东部时间（纽约）',
    keywords: '美国 东部 纽约',
  },
  {
    value: 'Europe/London',
    label: '英国时间（伦敦）',
    keywords: '英国 伦敦',
  },
  {
    value: 'Europe/Berlin',
    label: '中欧时间（柏林）',
    keywords: '欧洲 中欧 德国 柏林',
  },
  {
    value: 'Australia/Sydney',
    label: '澳大利亚东部时间（悉尼）',
    keywords: '澳大利亚 澳洲 东部 悉尼',
  },
  {
    value: 'Australia/Perth',
    label: '澳大利亚西部时间（珀斯）',
    keywords: '澳大利亚 澳洲 西部 珀斯',
  },
]

const timezoneById = new Map(
  COMMON_TIMEZONES.map((definition) => [definition.value, definition]),
)

export function getBrowserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
}

export function getTimezoneLabel(timezone: string): string {
  const known = timezoneById.get(timezone)
  if (known) return known.label
  return timezone === getBrowserTimezone()
    ? `当前设备时区（${timezone}）`
    : `其他时区（${timezone}）`
}

export function createTimezoneOptions(
  additionalTimezones: readonly string[] = [],
): TimezoneSelectOption[] {
  const browserTimezone = getBrowserTimezone()
  const ids = Array.from(
    new Set([
      ...COMMON_TIMEZONES.map((definition) => definition.value),
      browserTimezone,
      ...additionalTimezones.filter(Boolean),
    ]),
  )
  return ids.map((value) => {
    const definition = timezoneById.get(value)
    const label = getTimezoneLabel(value)
    return {
      value,
      label,
      searchText: `${label} ${value} ${definition?.keywords ?? ''}`.toLowerCase(),
    }
  })
}

export const filterTimezoneOption: SelectFilter = (pattern, option) => {
  const searchText =
    typeof option.searchText === 'string'
      ? option.searchText
      : `${String(option.label ?? '')} ${String(option.value ?? '')}`
  return searchText.toLowerCase().includes(pattern.trim().toLowerCase())
}
